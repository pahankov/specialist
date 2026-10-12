from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean, DateTime, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Notification(Base):
    """Internal bell notification: broadcast rows per recipient.

    No messenger binding needed — inbox lives in the app
    (master/super panels + client cabinet).
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_recipient_created", "recipient_id", "created_at"),
        Index("ix_notifications_recipient_unread", "recipient_id", "is_read"),
    )

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    text = Column(Text, nullable=False)
    audience = Column(String(20), nullable=True)
    # Deep-link key resolved per section on the client
    # ("appointments" → panel list / cabinet home).
    link = Column(String(50), nullable=True)  # all|masters|clients|my_clients|selected
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read_at = Column(DateTime(timezone=True), nullable=True)

    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])

    def __repr__(self):
        return f"<Notification to={self.recipient_id} read={self.is_read}>"
