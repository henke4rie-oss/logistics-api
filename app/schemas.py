"""
Pydantic v2 Data Validation & Serialization Schemas.
Enforces validation rules (positive weights, non-empty SKUs) and provides
ORM mode serialization via ConfigDict(from_attributes=True).
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ManifestBase(BaseModel):
    sku: str = Field(
        ...,
        min_length=3,
        max_length=64,
        description="Unique container item stock keeping unit",
        examples=["CNT-LON-9021"]
    )
    item_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Cargo item description",
        examples=["Industrial Lithium-Ion Power Modules"]
    )
    quantity: int = Field(
        ...,
        gt=0,
        description="Cargo piece count, must be >= 1",
        examples=[48]
    )
    destination: str = Field(
        ...,
        min_length=2,
        max_length=128,
        description="Destination port or warehouse location",
        examples=["Port of Rotterdam (NL)"]
    )
    weight_kg: float = Field(
        ...,
        gt=0.0,
        description="Gross cargo weight in kilograms",
        examples=[1840.5]
    )
    is_hazardous: bool = Field(
        default=False,
        description="Flag indicating dangerous goods (UN Hazmat classification)"
    )

    @field_validator("sku")
    @classmethod
    def clean_sku(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("SKU cannot be empty or whitespace")
        return cleaned


class ManifestCreate(ManifestBase):
    """Schema for registering a new container manifest."""
    pass


class ManifestUpdate(BaseModel):
    """Schema for updating manifest fields (all optional for partial updates)."""
    item_name: Optional[str] = Field(None, min_length=1, max_length=255)
    quantity: Optional[int] = Field(None, gt=0)
    destination: Optional[str] = Field(None, min_length=2, max_length=128)
    weight_kg: Optional[float] = Field(None, gt=0.0)
    is_hazardous: Optional[bool] = None


class ManifestResponse(ManifestBase):
    """Full manifest response serialized from SQLAlchemy ORM models."""
    id: int
    created_at: datetime
    updated_at: datetime

    # Pydantic v2 ORM compatibility
    model_config = ConfigDict(from_attributes=True)


class ManifestCreateSuccessResponse(BaseModel):
    message: str
    manifest: ManifestResponse


class BulkManifestRequest(BaseModel):
    items: List[Dict[str, Any]]
    atomic_mode: bool = Field(
        default=False,
        description="If True, rolls back entire batch if any item fails validation"
    )


class BulkItemError(BaseModel):
    row: int
    sku: Optional[str] = None
    error: str


class BulkManifestSummaryResponse(BaseModel):
    saved_count: int
    failed_count: int
    total_weight_kg: float
    hazardous_items: List[str]
    errors: List[BulkItemError]
    saved_manifests: List[ManifestResponse]


class ManifestStatsResponse(BaseModel):
    total_manifests: int
    total_quantity: int
    total_weight_kg: float
    average_weight_kg: float
    hazardous_count: int
    hazardous_percentage: float
    destinations_count: int
    destinations_breakdown: Dict[str, int]
