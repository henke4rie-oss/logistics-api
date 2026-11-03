"""
FastAPI Logistics Customs & Container Manifest Microservice
Production-grade implementation with SQLAlchemy ORM, Pydantic v2 validation,
and database connection pooling for SQLite and PostgreSQL.
"""

from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import get_db, engine
from app import models, schemas, crud

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes database tables on startup and disposes connection pool on shutdown.
    """
    yield
    # Properly close and dispose all pool connections on application shutdown
    engine.dispose()
    
app = FastAPI(
    title="Logistics Customs API",
    description="Backend microservice for container manifest validation, bulk customs clearing, and relational data integrity.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get(
    "/",
    tags=["System"],
    summary="Health Check",
    response_model=dict
)
def health_check():
    """Verify microservice status and runtime engine."""
    return {
        "status": "Online",
        "system": "Logistics Engine",
        "version": "1.0.0",
        "database_backend": engine.name,
    }


@app.get(
    "/manifests",
    response_model=List[schemas.ManifestResponse],
    tags=["Manifests"],
    summary="List Container Manifests",
)
def get_manifests(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=500, description="Page limit"),
    destination: Optional[str] = Query(None, description="Filter by destination port"),
    is_hazardous: Optional[bool] = Query(None, description="Filter hazardous materials only"),
    search: Optional[str] = Query(None, description="Search in SKU or Item Name"),
    db: Session = Depends(get_db),
):
    """
    Retrieve container manifests with optional pagination, text search,
    and customs compliance filtering.
    """
    return crud.get_manifests(
        db=db,
        skip=skip,
        limit=limit,
        destination=destination,
        is_hazardous=is_hazardous,
        search=search,
    )


@app.get(
    "/manifests/stats",
    response_model=schemas.ManifestStatsResponse,
    tags=["Manifests"],
    summary="Cargo & Customs Analytics",
)
def get_manifest_statistics(db: Session = Depends(get_db)):
    """Compute aggregate cargo metrics: total tonnage, hazardous ratio, destination volumes."""
    return crud.get_manifest_statistics(db=db)


@app.get(
    "/manifests/{sku}",
    response_model=schemas.ManifestResponse,
    tags=["Manifests"],
    summary="Get Manifest by SKU",
)
def get_manifest_by_sku(sku: str, db: Session = Depends(get_db)):
    """Lookup a single container item by unique SKU."""
    manifest = crud.get_manifest_by_sku(db=db, sku=sku)
    if not manifest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manifest with SKU '{sku}' not found",
        )
    return manifest


@app.post(
    "/manifests",
    response_model=schemas.ManifestCreateSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Manifests"],
    summary="Register Single Manifest",
)
def create_manifest(item: schemas.ManifestCreate, db: Session = Depends(get_db)):
    """
    Register a new container manifest item into the relational database.
    Validates unique SKU constraint and weight/quantity parameters.
    """
    existing = crud.get_manifest_by_sku(db=db, sku=item.sku)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Manifest with SKU '{item.sku}' already exists in database",
        )

    db_item = crud.create_manifest(db=db, manifest_in=item)
    return {
        "message": "Manifest registered successfully",
        "manifest": db_item,
    }


@app.put(
    "/manifests/{sku}",
    response_model=schemas.ManifestResponse,
    tags=["Manifests"],
    summary="Full Update of Manifest",
)
def update_manifest(
    sku: str,
    item_update: schemas.ManifestUpdate,
    db: Session = Depends(get_db),
):
    """Update all or subset of container manifest fields by SKU."""
    db_manifest = crud.get_manifest_by_sku(db=db, sku=sku)
    if not db_manifest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manifest with SKU '{sku}' not found",
        )

    return crud.update_manifest(db=db, db_manifest=db_manifest, manifest_in=item_update)


@app.delete(
    "/manifests/{sku}",
    status_code=status.HTTP_200_OK,
    tags=["Manifests"],
    summary="Delete Manifest Record",
)
def delete_manifest(sku: str, db: Session = Depends(get_db)):
    """Remove a container manifest from the database by SKU."""
    db_manifest = crud.get_manifest_by_sku(db=db, sku=sku)
    if not db_manifest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manifest with SKU '{sku}' not found",
        )

    crud.delete_manifest(db=db, db_manifest=db_manifest)
    return {"message": f"Manifest {sku} deleted successfully"}


@app.post(
    "/manifests/bulk",
    response_model=schemas.BulkManifestSummaryResponse,
    tags=["Manifests"],
    summary="Bulk Ingest Manifest Items",
)
def bulk_receive_manifests(
    payload: schemas.BulkManifestRequest,
    db: Session = Depends(get_db),
):
    """
    Bulk ingestion endpoint for maritime/freight container batches.
    Validates row-level constraints, reports malformed or duplicate rows,
    calculates aggregate gross weight, flags hazardous shipments,
    and commits valid records atomically.
    """
    return crud.process_bulk_manifests(
        db=db,
        items=payload.items,
        atomic_mode=payload.atomic_mode,
    )
