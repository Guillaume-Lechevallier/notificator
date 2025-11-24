from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    endpoint: str
    expirationTime: Optional[int] = None
    keys: PushSubscriptionKeys


class SubscriberCreate(BaseModel):
    subscription: PushSubscription
    label: Optional[str] = None
    user_agent: Optional[str] = None


class SubscriberResponse(BaseModel):
    id: int
    device_token: str
    label: Optional[str]
    endpoint: str
    created_at: datetime

    class Config:
        orm_mode = True


class NotificationCreate(BaseModel):
    title: str
    body: Optional[str] = None
    image_url: Optional[str] = None
    click_url: Optional[str] = None


class NotificationResponse(BaseModel):
    id: int
    title: str
    body: Optional[str]
    image_url: Optional[str]
    click_url: Optional[str]
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
