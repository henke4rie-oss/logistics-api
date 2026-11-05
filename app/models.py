"""This module defines the SQLAlchemy models for the logistics API application. It includes the ManifestModel and ManifestAuditLog classes, which represent the manifests and their associated audit logs in the database."""

# app/models.py
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, false
from sqlalchemy.orm import relationship
from app.database import Base

class ManifestModel(Base):
    __tablename__ = "manifests"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True, nullable=False)
    item_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    destination = Column(String, nullable=False)
    weight_kg = Column(Float, nullable=False)
    is_hazardous = Column(Boolean, nullable=False, default=False, server_default=false())
    
    # Required by Pydantic response schemas
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    audit_logs = relationship("ManifestAuditLog", back_populates="manifest", cascade="all, delete-orphan")


class ManifestAuditLog(Base):
    __tablename__ = "manifest_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    manifest_id = Column(Integer, ForeignKey("manifests.id"), nullable=False)
    action = Column(String, nullable=False)
    notes = Column(String, nullable=True)
    performed_by = Column(String, default="system")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    manifest = relationship("ManifestModel", back_populates="audit_logs")