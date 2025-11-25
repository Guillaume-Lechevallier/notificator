import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, index=True)
    device_token = Column(String(64), unique=True, index=True, default=lambda: uuid.uuid4().hex)
    label = Column(String(120), nullable=True)
    endpoint = Column(Text, unique=True, nullable=False)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    deliveries = relationship("Delivery", back_populates="subscriber", cascade="all, delete-orphan")
    business = relationship("Business", back_populates="subscriber", uselist=False)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    click_url = Column(Text, nullable=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    deliveries = relationship("Delivery", back_populates="notification", cascade="all, delete-orphan")
    business = relationship("Business", back_populates="notifications")


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    manager_name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(String(255), nullable=True)
    subscriber_id = Column(Integer, ForeignKey("subscribers.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscriber = relationship("Subscriber", back_populates="business")
    notifications = relationship("Notification", back_populates="business")


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
