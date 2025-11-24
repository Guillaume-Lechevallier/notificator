from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api", tags=["notifications"])


@router.post("/subscribers", response_model=schemas.SubscriberResponse)
def register_subscriber(payload: schemas.SubscriberCreate, db: Session = Depends(get_db)):
    device_token = uuid4().hex
    subscriber = models.Subscriber(device_token=device_token)
    db.add(subscriber)
    db.commit()
    db.refresh(subscriber)
    return subscriber


@router.get("/notifications", response_model=list[schemas.NotificationResponse])
def list_notifications(db: Session = Depends(get_db)):
    return db.query(models.Notification).order_by(models.Notification.created_at.desc()).all()


@router.post("/notifications", response_model=schemas.NotificationResponse)
def send_notification(payload: schemas.NotificationCreate, db: Session = Depends(get_db)):
    notification = models.Notification(title=payload.title, body=payload.body)
    db.add(notification)
    db.flush()

    subscribers = db.query(models.Subscriber).all()
    for subscriber in subscribers:
        delivery = models.Delivery(
            notification=notification,
            subscriber=subscriber,
        )
        db.add(delivery)

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
