from sqlalchemy import String, Boolean, DateTime, Integer, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import uuid
from app.database import Base

class SystemSetting(Base):
    __tablename__ = "settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

class FileUpload(Base):
    __tablename__ = "file_uploads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    uploaded_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Country(Base):
    __tablename__ = "countries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    iso_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    phone_code: Mapped[Optional[str]] = mapped_column(String(20))

class State(Base):
    __tablename__ = "states"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    country_id: Mapped[str] = mapped_column(String, ForeignKey("countries.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    state_code: Mapped[Optional[str]] = mapped_column(String(20))

class City(Base):
    __tablename__ = "cities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    state_id: Mapped[str] = mapped_column(String, ForeignKey("states.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

class Currency(Base):
    __tablename__ = "currencies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)

class Language(Base):
    __tablename__ = "languages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

class Timezone(Base):
    __tablename__ = "timezones"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    utc_offset: Mapped[str] = mapped_column(String(20), nullable=False)
