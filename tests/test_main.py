"""
Test Suite for FastAPI Logistics Microservice.
Uses in-memory SQLite database isolation with FastAPI TestClient.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# In-memory SQLite engine for fast, isolated unit and integration testing
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override FastAPI's database dependency for testing
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_database():
    """Ensure a fresh in-memory database state for every single test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    """Provide an isolated TestClient instance per test."""
    with TestClient(app) as c:
        yield c

def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "Online"


def test_create_and_get_manifest(client):
    payload = {
        "sku": "CNT-TEST-001",
        "item_name": "Precision Sensor Unit",
        "quantity": 10,
        "destination": "Port of Rotterdam",
        "weight_kg": 250.5,
        "is_hazardous": False,
    }
    # 1. Create manifest
    create_res = client.post("/manifests", json=payload)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["manifest"]["sku"] == "CNT-TEST-001"
    assert data["manifest"]["id"] == 1

    # 2. Duplicate SKU rejection
    dup_res = client.post("/manifests", json=payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"]

    # 3. Lookup by SKU
    get_res = client.get("/manifests/CNT-TEST-001")
    assert get_res.status_code == 200
    assert get_res.json()["item_name"] == "Precision Sensor Unit"


def test_bulk_manifest_ingestion(client):
    batch = {
        "items": [
            {
                "sku": "BULK-001",
                "item_name": "Battery Packs",
                "quantity": 20,
                "destination": "Port of Hamburg",
                "weight_kg": 800.0,
                "is_hazardous": True,
            },
            {
                "sku": "BULK-002",
                "item_name": "Auto Cables",
                "quantity": 50,
                "destination": "Port of Antwerp",
                "weight_kg": 400.0,
                "is_hazardous": False,
            },
            {
                # Invalid quantity
                "sku": "BULK-003",
                "item_name": "Broken Cargo",
                "quantity": -5,
                "destination": "Port of Antwerp",
                "weight_kg": 100.0,
            }
        ],
        "atomic_mode": False
    }

    res = client.post("/manifests/bulk", json=batch)
    assert res.status_code == 200
    summary = res.json()
    assert summary["saved_count"] == 2
    assert summary["failed_count"] == 1
    assert summary["total_weight_kg"] == 1200.0
    assert summary["hazardous_items"] == ["BULK-001"]
    assert len(summary["errors"]) == 1


def test_stats_analytics(client):
    # Ingest 1 non-hazardous and 1 hazardous
    client.post("/manifests", json={
        "sku": "ST-01", "item_name": "General Freight",
        "quantity": 10, "destination": "Port A", "weight_kg": 100.0, "is_hazardous": False
    })
    client.post("/manifests", json={
        "sku": "ST-02", "item_name": "Chemical Drum",
        "quantity": 5, "destination": "Port B", "weight_kg": 300.0, "is_hazardous": True
    })

    res = client.get("/manifests/stats")
    assert res.status_code == 200
    stats = res.json()
    assert stats["total_manifests"] == 2
    assert stats["total_weight_kg"] == 400.0
    assert stats["hazardous_count"] == 1
    assert stats["hazardous_percentage"] == 50.0

    # tests/test_main.py

def test_duplicate_sku_rejection(client):
    """Ensure inserting a manifest with an existing SKU gets rejected."""
    payload = {
        "sku": "DUP-TEST-01",
        "item_name": "Test Cargo",
        "quantity": 10,
        "destination": "Port X",
        "weight_kg": 100.0,
        "is_hazardous": False,
    }
    # Initial creation returns 201 Created, not 200 OK
    res1 = client.post("/manifests", json=payload)
    assert res1.status_code == 201

    # Duplicate SKU creation should fail with a conflict/bad request
    res2 = client.post("/manifests", json=payload)
    assert res2.status_code in [400, 409, 422]