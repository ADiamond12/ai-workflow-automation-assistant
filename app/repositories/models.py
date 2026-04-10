import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.domain.enums import (
    CustomerTier,
    IntakeChannel,
    PriorityLevel,
    RecommendedAction,
    RecommendedTeam,
    RequestCategory,
    ReviewStatus,
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class RequestRecord(TimestampMixin, Base):
    __tablename__ = "requests"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    sender_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[IntakeChannel] = mapped_column(
        Enum(IntakeChannel, native_enum=False), nullable=False
    )
    customer_tier: Mapped[CustomerTier] = mapped_column(
        Enum(CustomerTier, native_enum=False),
        nullable=False,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    urgency_hint: Mapped[str | None] = mapped_column(String(300), nullable=True)

    decisions: Mapped[list["DecisionRecord"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["ReviewRecord"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class DecisionRecord(TimestampMixin, Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    request_id: Mapped[str] = mapped_column(
        ForeignKey("requests.id"),
        nullable=False,
        index=True,
    )
    category: Mapped[RequestCategory] = mapped_column(
        Enum(RequestCategory, native_enum=False),
        nullable=False,
    )
    priority: Mapped[PriorityLevel] = mapped_column(
        Enum(PriorityLevel, native_enum=False), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_team: Mapped[RecommendedTeam] = mapped_column(
        Enum(RecommendedTeam, native_enum=False),
        nullable=False,
    )
    recommended_action: Mapped[RecommendedAction] = mapped_column(
        Enum(RecommendedAction, native_enum=False),
        nullable=False,
    )
    missing_information: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, native_enum=False),
        default=ReviewStatus.PENDING,
        nullable=False,
    )
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    token_usage: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    request: Mapped["RequestRecord"] = relationship(back_populates="decisions")
    reviews: Mapped[list["ReviewRecord"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )


class ReviewRecord(TimestampMixin, Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    request_id: Mapped[str] = mapped_column(
        ForeignKey("requests.id"),
        nullable=False,
        index=True,
    )
    decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("decisions.id"), nullable=True, index=True
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, native_enum=False),
        nullable=False,
    )
    reviewer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    request: Mapped["RequestRecord"] = relationship(back_populates="reviews")
    decision: Mapped["DecisionRecord"] = relationship(back_populates="reviews")
