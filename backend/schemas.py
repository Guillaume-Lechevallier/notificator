from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, HttpUrl


class SubscriberCreate(BaseModel):
    email: Optional[str] = None


class SubscriberResponse(BaseModel):
    id: int
    device_token: str
    email: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class NotificationCreate(BaseModel):
    title: str
    body: Optional[str] = None
    image_url: HttpUrl
    target_url: HttpUrl


class NotificationResponse(BaseModel):
    id: int
    title: str
    body: Optional[str]
    image_url: HttpUrl
    target_url: HttpUrl
    created_at: datetime

    class Config:
        orm_mode = True


class DeliveryResponse(BaseModel):
    id: int
    status: str
    delivered_at: Optional[datetime]
    opened_at: Optional[datetime]
    notification: NotificationResponse

    class Config:
        orm_mode = True


class DeliveryList(BaseModel):
    notifications: List[DeliveryResponse]
