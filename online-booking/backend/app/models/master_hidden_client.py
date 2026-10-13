"""MasterHiddenClient — a master removed a client from their own lists.

The client row stays intact (other masters, own login, history). Past
appointments with this master are kept but rendered as DELETED_CLIENT_NAME.
A new booking with this master revives visibility (unhide).
"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime, Boolean, String, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

DELETED_CLIENT_NAME = "Удалённый клиент"


class MasterHiddenClient(Base):
    __tablename__ = "master_hidden_clients"
    __table_args__ = (
        UniqueConstraint('master_profile_id', 'client_profile_id'),
        Index('ix_hidden_by_master', 'master_profile_id'),
    )

    id = Column(Integer, primary_key=True)
    master_profile_id = Column(Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"),
                               nullable=False)
    client_profile_id = Column(Integer, ForeignKey("client_profiles.id", ondelete="CASCADE"),
                               nullable=False)
    hidden_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # Archive reason (master's own bookkeeping): moved | left | inactive |
    # deceased | other. NULL = hidden without a reason (legacy rows).
    hidden_reason = Column(String(30), nullable=True)
    # Blacklist cause (master picks from a list): no_show | rude | spam |
    # debt | other. block_note carries the free text for "other" (or any
    # extra context). NULL when merely archived.
    block_reason = Column(String(30), nullable=True)
    block_note = Column(String(500), nullable=True)
    # Blacklist: hidden AND barred from new bookings with this master.
    # Plain hides (via clients DELETE) leave is_blocked False.
    is_blocked = Column(Boolean, default=False, nullable=False)
    blocked_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return (f"<MasterHiddenClient(master_profile_id={self.master_profile_id}, "
                f"client_profile_id={self.client_profile_id})>")
