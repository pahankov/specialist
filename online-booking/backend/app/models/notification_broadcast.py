from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Index, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class NotificationBroadcast(Base):
    """Sent-broadcast history: what/when/to-whom (one row per send).

    Per-recipient inbox rows live in `notifications`; this table answers
    "какие, когда и кому я отправлял" without regrouping them.
    Recipients are snapshotted as [{id, name}] — names stay readable even
    if users are renamed later.
    """

    __tablename__ = "notification_broadcasts"
    __table_args__ = (
        Index("ix_broadcasts_sender_created", "sender_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    audience = Column(String(20), nullable=False)
    text = Column(Text, nullable=False)
    recipients = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sender = relationship("User", foreign_keys=[sender_id])

    def __repr__(self):
        return f"<Broadcast {self.id} {self.audience} x{len(self.recipients or [])}>"
