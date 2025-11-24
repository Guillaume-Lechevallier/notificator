import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, index=True)
    device_token = Column(String(64), unique=True, index=True, default=lambda: uuid.uuid4().hex)
    created_at = Column(DateTime, default=datetime.utcnow)

    deliveries = relationship("Delivery", back_populates="subscriber", cascade="all, delete-orphan")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    deliveries = relationship("Delivery", back_populates="notification", cascade="all, delete-orphan")


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint("notification_id", "subscriber_id", name="uq_delivery_notification_subscriber"),
    )

    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(Integer, ForeignKey("notifications.id", ondelete="CASCADE"))
    subscriber_id = Column(Integer, ForeignKey("subscribers.id", ondelete="CASCADE"))
    status = Column(String(32), default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)

    notification = relationship("Notification", back_populates="deliveries")
    subscriber = relationship("Subscriber", back_populates="deliveries")


class HealthCheck(Base):
    __tablename__ = "health_checks"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
