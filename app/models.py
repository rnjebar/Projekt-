from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .db import Base

class Product(Base):
    __tablename__ = "products"

    art_nr: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    beschreibung_quelle: Mapped[str] = mapped_column(Text, default="")
    prompt_ergaenzungen: Mapped[str] = mapped_column(Text, default="")

    beschreibung_generiert: Mapped[str] = mapped_column(Text, default="")
    beschreibung_final: Mapped[str] = mapped_column(Text, default="")

    review_status: Mapped[str] = mapped_column(String(30), default="pending")  # pending/in_review/approved/rejected
    qa_notes: Mapped[str] = mapped_column(Text, default="")

    locked_by: Mapped[str] = mapped_column(String(255), default="")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    updated_by: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)