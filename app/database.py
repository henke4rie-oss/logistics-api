"""This module is responsible for setting up the database connection and providing a session for interacting with the database.
It uses SQLAlchemy to create an engine and a session factory, which can be used to create sessions for database operations. The database URL is obtained from the application settings.
"""

import os
from app.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()