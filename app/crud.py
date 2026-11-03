"""
CRUD & Relational Data Access Operations.
Encapsulates all SQLAlchemy queries, transactions, and aggregation math.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from pydantic import ValidationError

from app import models, schemas


def get_manifest_by_sku(db: Session, sku: str) -> Optional[models.ManifestModel]:
    return db.query(models.ManifestModel).filter(
        models.ManifestModel.sku == sku.strip().upper()
    ).first()


def get_manifest_by_id(db: Session, manifest_id: int) -> Optional[models.ManifestModel]:
    return db.query(models.ManifestModel).filter(models.ManifestModel.id == manifest_id).first()


def get_manifests(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    destination: Optional[str] = None,
    is_hazardous: Optional[bool] = None,
    search: Optional[str] = None,
) -> List[models.ManifestModel]:
    query = db.query(models.ManifestModel)

    if destination:
        query = query.filter(models.ManifestModel.destination.ilike(f"%{destination}%"))
    if is_hazardous is not None:
        query = query.filter(models.ManifestModel.is_hazardous == is_hazardous)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                models.ManifestModel.sku.ilike(search_filter),
                models.ManifestModel.item_name.ilike(search_filter),
                models.ManifestModel.destination.ilike(search_filter),
            )
        )

    return query.order_by(models.ManifestModel.id.desc()).offset(skip).limit(limit).all()


def create_manifest(db: Session, manifest_in: schemas.ManifestCreate) -> models.ManifestModel:
    db_item = models.ManifestModel(**manifest_in.model_dump())
    db.add(db_item)
    
    # Audit log creation
    audit = models.ManifestAuditLog(
        manifest=db_item,
        action="CREATED",
        notes=f"Initial registration for destination {db_item.destination}",
        performed_by="customs_agent"
    )
    db.add(audit)
    
    db.commit()
    db.refresh(db_item)
    return db_item


def update_manifest(
    db: Session,
    db_manifest: models.ManifestModel,
    manifest_in: schemas.ManifestUpdate,
) -> models.ManifestModel:
    update_data = manifest_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_manifest, field, value)

    audit = models.ManifestAuditLog(
        manifest_id=db_manifest.id,
        action="UPDATED",
        notes=f"Updated fields: {list(update_data.keys())}",
        performed_by="customs_agent"
    )
    db.add(audit)

    db.commit()
    db.refresh(db_manifest)
    return db_manifest


def delete_manifest(db: Session, db_manifest: models.ManifestModel) -> None:
    db.delete(db_manifest)
    db.commit()


def process_bulk_manifests(
    db: Session,
    items: List[Dict[str, Any]],
    atomic_mode: bool = False,
) -> schemas.BulkManifestSummaryResponse:
    """
    Ingests bulk manifest entries safely within database transaction boundaries.
    """
    successful_models: List[models.ManifestModel] = []
    errors: List[schemas.BulkItemError] = []
    total_weight = 0.0
    hazardous_skus: List[str] = []
    seen_in_batch = set()

    for index, raw_item in enumerate(items):
        try:
            # 1. Pydantic validation
            parsed_item = schemas.ManifestCreate(**raw_item)
            sku = parsed_item.sku

            # 2. Duplicate checking
            if sku in seen_in_batch:
                errors.append(schemas.BulkItemError(
                    row=index,
                    sku=sku,
                    error=f"Duplicate SKU '{sku}' within batch"
                ))
                continue

            existing = get_manifest_by_sku(db, sku)
            if existing:
                errors.append(schemas.BulkItemError(
                    row=index,
                    sku=sku,
                    error=f"SKU '{sku}' already exists in database"
                ))
                continue

            # 3. Model staging
            seen_in_batch.add(sku)
            db_item = models.ManifestModel(**parsed_item.model_dump())
            db.add(db_item)
            successful_models.append(db_item)
            total_weight += db_item.weight_kg

            if db_item.is_hazardous:
                hazardous_skus.append(db_item.sku)

        except ValidationError as val_err:
            errors.append(schemas.BulkItemError(
                row=index,
                sku=raw_item.get("sku"),
                error="; ".join([f"{e['loc'][-1]}: {e['msg']}" for e in val_err.errors()])
            ))
        except Exception as e:
            errors.append(schemas.BulkItemError(
                row=index,
                sku=raw_item.get("sku"),
                error=str(e)
            ))

    # If atomic mode is requested and any error occurred, abort entire transaction
    if atomic_mode and errors:
        db.rollback()
        return schemas.BulkManifestSummaryResponse(
            saved_count=0,
            failed_count=len(items),
            total_weight_kg=0.0,
            hazardous_items=[],
            errors=errors,
            saved_manifests=[],
        )

    # Commit valid items to the relational database
    try:
        db.commit()
        for item in successful_models:
            db.refresh(item)
    except Exception as commit_exc:
        db.rollback()
        raise commit_exc

    return schemas.BulkManifestSummaryResponse(
        saved_count=len(successful_models),
        failed_count=len(errors),
        total_weight_kg=round(total_weight, 2),
        hazardous_items=hazardous_skus,
        errors=errors,
        saved_manifests=successful_models,
    )


def get_manifest_statistics(db: Session) -> schemas.ManifestStatsResponse:
    """Computes high-performance aggregate cargo analytics."""
    total_manifests = db.query(models.ManifestModel).count()
    if total_manifests == 0:
        return schemas.ManifestStatsResponse(
            total_manifests=0,
            total_quantity=0,
            total_weight_kg=0.0,
            average_weight_kg=0.0,
            hazardous_count=0,
            hazardous_percentage=0.0,
            destinations_count=0,
            destinations_breakdown={},
        )

    aggregates = db.query(
        func.sum(models.ManifestModel.quantity).label("total_qty"),
        func.sum(models.ManifestModel.weight_kg).label("total_wt"),
        func.avg(models.ManifestModel.weight_kg).label("avg_wt"),
    ).first()

    hazardous_count = db.query(models.ManifestModel).filter(
        models.ManifestModel.is_hazardous == True
    ).count()

    dest_rows = db.query(
        models.ManifestModel.destination,
        func.count(models.ManifestModel.id)
    ).group_by(models.ManifestModel.destination).all()

    dest_breakdown = {dest: count for dest, count in dest_rows}

    total_wt = float(aggregates.total_wt or 0.0)
    avg_wt = float(aggregates.avg_wt or 0.0)
    total_qty = int(aggregates.total_qty or 0)

    return schemas.ManifestStatsResponse(
        total_manifests=total_manifests,
        total_quantity=total_qty,
        total_weight_kg=round(total_wt, 2),
        average_weight_kg=round(avg_wt, 2),
        hazardous_count=hazardous_count,
        hazardous_percentage=round((hazardous_count / total_manifests) * 100, 1),
        destinations_count=len(dest_breakdown),
        destinations_breakdown=dest_breakdown,
    )
