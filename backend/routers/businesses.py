import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/businesses", tags=["businesses"])


def _get_subscriber(db: Session, subscriber_id: int) -> models.Subscriber:
    subscriber = db.query(models.Subscriber).filter(models.Subscriber.id == subscriber_id).first()
    if not subscriber:
        raise HTTPException(status_code=404, detail="Abonné introuvable pour ce commerce")
    return subscriber


@router.get("", response_model=list[schemas.BusinessResponse])
def list_businesses(db: Session = Depends(get_db)):
    return db.query(models.Business).order_by(models.Business.created_at.desc()).all()


@router.post("", response_model=schemas.BusinessResponse, status_code=201)
def create_business(payload: schemas.BusinessCreate, db: Session = Depends(get_db)):
    subscriber = None
    if payload.subscriber_id:
        subscriber = _get_subscriber(db, payload.subscriber_id)

    business = models.Business(
        name=payload.name,
        manager_name=payload.manager_name,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        subscriber=subscriber,
    )
    db.add(business)
    db.commit()
    db.refresh(business)
    return business


@router.get("/{business_id}", response_model=schemas.BusinessResponse)
def get_business(business_id: int, db: Session = Depends(get_db)):
    business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Commerce introuvable")
    return business


@router.put("/{business_id}", response_model=schemas.BusinessResponse)
def update_business(business_id: int, payload: schemas.BusinessUpdate, db: Session = Depends(get_db)):
    business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Commerce introuvable")

    data = payload.dict(exclude_unset=True)
    subscriber = None
    if "subscriber_id" in data:
        subscriber_id = data.pop("subscriber_id")
        if subscriber_id is not None:
            subscriber = _get_subscriber(db, subscriber_id)
        business.subscriber = subscriber

    for field, value in data.items():
        setattr(business, field, value)

    business.updated_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(business)
    return business
