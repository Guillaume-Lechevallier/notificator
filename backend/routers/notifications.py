import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from uuid import uuid4
import mimetypes

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from cryptography.hazmat.primitives import serialization
from py_vapid import b64urlencode
from pywebpush import Vapid, WebPushException, webpush

router = APIRouter(prefix="/api", tags=["notifications"])


DEFAULT_VAPID_CLAIM = "mailto:moilechevallier@gmail.com"
VAPID_STORE = Path(__file__).resolve().parent.parent / ".vapid_keys.json"
BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "frontend" / "uploads"
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def _load_vapid_from_env() -> dict[str, str] | None:
    public = os.getenv("VAPID_PUBLIC_KEY")
    private = os.getenv("VAPID_PRIVATE_KEY")
    claim = os.getenv("VAPID_CLAIM_EMAIL", DEFAULT_VAPID_CLAIM)

    if public and private:
        return {"public": public, "private": private, "claim": claim}
    return None


def _load_vapid_from_file() -> dict[str, str] | None:
    if not VAPID_STORE.exists():
        return None

    try:
        data = json.loads(VAPID_STORE.read_text())
    except (OSError, json.JSONDecodeError):
        return None

    public = data.get("public")
    private = data.get("private")
    claim = data.get("claim", DEFAULT_VAPID_CLAIM)

    if public and private:
        return {"public": public, "private": private, "claim": claim}
    return None


def _persist_vapid_keys(keys: dict[str, str]) -> None:
    try:
        VAPID_STORE.write_text(json.dumps(keys, indent=2))
    except OSError:
        # In read-only environments, fall back to in-memory values only.
        pass


def _generate_vapid_keys() -> dict[str, str]:
    vapid = Vapid()
    vapid.generate_keys()

    claim = os.getenv("VAPID_CLAIM_EMAIL", DEFAULT_VAPID_CLAIM)

    def _b64urlencode_bytes(data: bytes) -> str:
        encoded = b64urlencode(data)
        return encoded if isinstance(encoded, str) else encoded.decode()

    private_value = vapid.private_key.private_numbers().private_value
    private_bytes = private_value.to_bytes(32, byteorder="big")
    public_bytes = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )

    private = _b64urlencode_bytes(private_bytes)
    public = _b64urlencode_bytes(public_bytes)

    keys = {"public": public, "private": private, "claim": claim}
    _persist_vapid_keys(keys)
    return keys


def _get_vapid_settings():
    vapid = _load_vapid_from_env() or _load_vapid_from_file()

    if vapid:
        return vapid

    return _generate_vapid_keys()


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
    )


@router.get("/config")
def get_public_config():
    vapid = _get_vapid_settings()
    return {"public_key": vapid["public"]}


@router.post("/uploads", response_model=schemas.UploadResponse)
def upload_image(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Format d'image non supporté")

    suffix = Path(file.filename or "").suffix
    if not suffix:
        guessed = mimetypes.guess_extension(file.content_type or "")
        suffix = guessed or ""

    filename = f"{uuid4().hex}{suffix}"
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        destination = UPLOAD_DIR / filename
        with destination.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except OSError:
        raise HTTPException(status_code=500, detail="Impossible d'enregistrer l'image envoyée")

    return {"url": f"/uploads/{filename}"}


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

    if existing and payload.business_id is None:
        existing.label = payload.label or existing.label
        existing.user_agent = payload.user_agent or existing.user_agent
        db.commit()
        db.refresh(existing)
        return existing

    if existing and business and business.subscriber_id == existing.id:
        existing.label = payload.label or existing.label
        existing.user_agent = payload.user_agent or existing.user_agent
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
