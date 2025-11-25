import json
import os
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from pywebpush import WebPushException, webpush

router = APIRouter(prefix="/api", tags=["notifications"])


def _get_vapid_settings():
    public = os.getenv("VAPID_PUBLIC_KEY")
    private = os.getenv("VAPID_PRIVATE_KEY")
    claim = os.getenv("VAPID_CLAIM_EMAIL", "mailto:admin@example.com")

    if not public or not private:
        raise HTTPException(status_code=500, detail="Les clefs VAPID ne sont pas configurées")

    return {"public": public, "private": private, "claim": claim}


def _send_push(
    subscriber: models.Subscriber,
    notification: models.Notification,
    vapid: dict[str, str],
):
    payload = {
        "title": notification.title,
        "body": notification.body or "",
        "image": notification.image_url,
        "url": notification.click_url
        or f"/notification.html?image={notification.image_url or ''}&target={notification.click_url or ''}",
        "tag": f"notificator-{notification.id}",
    }

    webpush(
        subscription_info={
            "endpoint": subscriber.endpoint,
            "keys": {"p256dh": subscriber.p256dh, "auth": subscriber.auth},
        },
        data=json.dumps(payload),
        vapid_private_key=vapid["private"],
        vapid_claims={"sub": vapid["claim"]},
        vapid_public_key=vapid["public"],
    )


@router.get("/config")
def get_public_config():
    public = os.getenv("VAPID_PUBLIC_KEY")
    if not public:
        raise HTTPException(status_code=500, detail="Clé publique VAPID manquante")
    return {"public_key": public}


@router.post("/subscribers", response_model=schemas.SubscriberResponse)
def register_subscriber(payload: schemas.SubscriberCreate, db: Session = Depends(get_db)):
    subscription = payload.subscription
    business = None
    if payload.business_id is not None:
        business = (
            db.query(models.Business)
            .filter(models.Business.id == payload.business_id)
            .first()
        )
        if not business:
            raise HTTPException(status_code=404, detail="Commerce associé introuvable")

    existing = (
        db.query(models.Subscriber)
        .filter(models.Subscriber.endpoint == subscription.endpoint)
        .first()
    )

    if existing:
        existing.label = payload.label or existing.label
        existing.user_agent = payload.user_agent or existing.user_agent
        if business:
            business.subscriber = existing
        db.commit()
        db.refresh(existing)
        return existing

    subscriber = models.Subscriber(
        device_token=uuid4().hex,
        label=payload.label,
        endpoint=subscription.endpoint,
        p256dh=subscription.keys.p256dh,
        auth=subscription.keys.auth,
        user_agent=payload.user_agent,
    )
    db.add(subscriber)
    db.flush()
    if business:
        business.subscriber = subscriber
    db.commit()
    db.refresh(subscriber)
    return subscriber


@router.get("/subscribers", response_model=list[schemas.SubscriberResponse])
def list_subscribers(db: Session = Depends(get_db)):
    return db.query(models.Subscriber).order_by(models.Subscriber.created_at.desc()).all()


@router.get("/notifications", response_model=list[schemas.NotificationResponse])
def list_notifications(db: Session = Depends(get_db)):
    return db.query(models.Notification).order_by(models.Notification.created_at.desc()).all()


@router.post("/notifications", response_model=schemas.NotificationResponse)
def send_notification(payload: schemas.NotificationCreate, db: Session = Depends(get_db)):
    business = None
    subscribers: list[models.Subscriber]

    if payload.business_id:
        business = db.query(models.Business).filter(models.Business.id == payload.business_id).first()
        if not business:
            raise HTTPException(status_code=404, detail="Commerce ciblé introuvable")
        if not business.subscriber:
            raise HTTPException(status_code=400, detail="Ce commerce n'est associé à aucun abonné push")
        subscribers = [business.subscriber]
    else:
        subscribers = db.query(models.Subscriber).all()

    if not subscribers:
        raise HTTPException(status_code=400, detail="Aucun destinataire disponible pour l'envoi")

    notification = models.Notification(
        title=payload.title,
        body=payload.body,
        image_url=payload.image_url,
        click_url=payload.click_url,
        business=business,
    )
    db.add(notification)
    db.flush()

    vapid = _get_vapid_settings()
    for subscriber in subscribers:
        delivery = models.Delivery(
            notification=notification,
            subscriber=subscriber,
        )
        db.add(delivery)
        try:
            _send_push(subscriber, notification, vapid)
            delivery.status = "delivered"
            delivery.delivered_at = datetime.utcnow()
        except WebPushException:
            delivery.status = "failed"

    db.commit()
    db.refresh(notification)
    return notification


@router.get("/push/{device_token}", response_model=schemas.DeliveryList)
def fetch_notifications(device_token: str, db: Session = Depends(get_db)):
    subscriber = (
        db.query(models.Subscriber)
        .filter(models.Subscriber.device_token == device_token)
        .first()
    )
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    deliveries = (
        db.query(models.Delivery)
        .filter(models.Delivery.subscriber == subscriber)
        .order_by(models.Delivery.created_at.desc())
        .all()
    )
    return schemas.DeliveryList(
        notifications=[
            schemas.DeliveryResponse(
                id=delivery.id,
                status=delivery.status,
                delivered_at=delivery.delivered_at,
                opened_at=delivery.opened_at,
                notification=delivery.notification,
            )
            for delivery in deliveries
        ]
    )


@router.post("/push/{delivery_id}/delivered")
def mark_delivered(delivery_id: int, db: Session = Depends(get_db)):
    delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    delivery.status = "delivered"
    delivery.delivered_at = datetime.utcnow()
    db.commit()
    return {"status": "ok"}


@router.post("/push/{delivery_id}/opened")
def mark_opened(delivery_id: int, db: Session = Depends(get_db)):
    delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    delivery.status = "opened"
    delivery.opened_at = datetime.utcnow()
    db.commit()
    return {"status": "ok"}
