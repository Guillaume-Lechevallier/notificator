from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


DEFAULT_SETTINGS: Dict[str, str] = {
    "enrollment_prompt": "Activer les alertes de votre commerçant ?",
}


def _get_setting(db: Session, key: str) -> models.Setting:
    setting = db.query(models.Setting).filter(models.Setting.key == key).first()
    if setting:
        return setting

    default_value = DEFAULT_SETTINGS.get(key)
    if default_value is None:
        raise HTTPException(status_code=404, detail="Clé de paramètre inconnue")

    setting = models.Setting(key=key, value=default_value, created_at=datetime.utcnow())
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


@router.get("/{key}", response_model=schemas.SettingResponse)
def read_setting(key: str, db: Session = Depends(get_db)):
    return _get_setting(db, key)


@router.put("/{key}", response_model=schemas.SettingResponse)
def update_setting(key: str, payload: schemas.SettingUpdate, db: Session = Depends(get_db)):
    if key not in DEFAULT_SETTINGS:
        raise HTTPException(status_code=404, detail="Clé de paramètre inconnue")

    value = payload.value.strip()
    if not value:
        raise HTTPException(status_code=422, detail="Le contenu du paramètre est requis")

    setting = db.query(models.Setting).filter(models.Setting.key == key).first()
    if setting:
        setting.value = value
        setting.updated_at = datetime.utcnow()
    else:
        setting = models.Setting(key=key, value=value, created_at=datetime.utcnow())
        db.add(setting)

    db.commit()
    db.refresh(setting)
    return setting
