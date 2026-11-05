# Logistics API

Containerized FastAPI service for managing customs and container manifest data. Handles standard CRUD, bulk ingestion with row-level validation, audit logging, and cargo analytics.

## Tech Stack

| Layer | Tech |
| --- | --- |
| Language | Python 3.12 |
| Framework | FastAPI |
| Database | PostgreSQL 16 (SQLAlchemy ORM) |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Testing | Pytest (FastAPI TestClient) |
| Infrastructure | Docker, Docker Compose |

## Features

* SKU-keyed CRUD operations for container manifests.
* Bulk ingestion endpoint with per-row validation, duplicate handling, and optional `atomic_mode` transaction rollback.
* Query filtering, text search, and pagination on list routes.
* Aggregate stats: gross weight totals, hazardous goods ratios, and volume broken down by destination.
* Audit logging triggered on write and update operations.
* Automated database schema migrations via Alembic on container start.

## Quick Start

Prerequisites: Docker and Docker Compose.

```bash
git clone https://github.com/henke4rie-oss/logistics-api.git
cd logistics-api
docker compose up --build
```

The Compose setup boots PostgreSQL, waits for the healthcheck to pass, executes migrations, and starts the Uvicorn server.

* API Base: http://localhost:8000
* OpenAPI Docs: http://localhost:8000/docs

Database configuration defaults to `customs_user` / `customs_pass` / `customs_manifests`. Override these values using `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` inside a `.env` file.

### Example Requests

```bash
# Create a manifest entry
curl -X POST http://localhost:8000/manifests \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "CNT-LON-9021", 
    "item_name": "Lithium-Ion Power Modules", 
    "quantity": 48, 
    "destination": "Port of Rotterdam (NL)", 
    "weight_kg": 1840.5, 
    "is_hazardous": true
  }'

# Fetch aggregate statistics
curl http://localhost:8000/manifests/stats
```

## API Reference

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Service healthcheck |
| `GET` | `/manifests` | List entries (Params: `skip`, `limit`, `destination`, `is_hazardous`, `search`) |
| `GET` | `/manifests/stats` | Return aggregate cargo metrics |
| `GET` | `/manifests/{sku}` | Fetch single manifest by SKU |
| `POST` | `/manifests` | Create manifest record (returns 400 on duplicate SKU) |
| `PUT` | `/manifests/{sku}` | Partial update (omitted fields remain unchanged; explicitly sending `null` returns 422) |
| `DELETE` | `/manifests/{sku}` | Remove manifest record |
| `POST` | `/manifests/bulk` | Ingest multiple manifests with per-row failure reports |

## Local Development & Testing

Tests run against an in-memory SQLite database and do not require Docker to execute.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

## Database Migrations

Migrations execute automatically when launching the `api` container. To run migrations manually inside the running container:

```bash
docker compose exec api alembic upgrade head
```

To generate a new migration revision locally after updating `app/models.py`:

```bash
DATABASE_URL=postgresql://customs_user:customs_pass@localhost:5433/customs_manifests \
  alembic revision --autogenerate -m "describe_change"
```

## Project Structure

```text
app/
  main.py        Route handlers and middleware initialization
  schemas.py     Pydantic request and response contracts
  models.py      SQLAlchemy table definitions
  crud.py        Database queries and operations
  database.py    Engine config and session factory
  config.py      Environment settings parsing
alembic/         Schema migration scripts
tests/           Pytest suite
```

## Production Considerations

* Authentication is not implemented in the app. 
* CORS configuration accepts all origin headers (`*`) with credentials disabled (`allow_credentials=False`).
* Test suites default to SQLite for isolation and execution speed; the core runtime explicitly targets PostgreSQL 16.