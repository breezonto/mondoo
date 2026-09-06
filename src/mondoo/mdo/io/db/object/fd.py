"""
File metadata model.

This module defines the database representation of a file descriptor.
The actual file content is stored externally (e.g. filesystem, OSS/S3),
while PostgreSQL stores its metadata.
"""
from mondoo.configurator import FD_TABLE

from collections.abc import Generator
from datetime import datetime
from uuid     import UUID, uuid4

from sqlalchemy                     import BigInteger, DateTime, String, Text, create_engine
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm                 import DeclarativeBase, Mapped, mapped_column, sessionmaker

import os

PSQL_HOST  = os.getenv('PSQL_HOST', 'localhost')
PSQL_PORT  = os.getenv('PSQL_PORT', 5432)
PSQL_DB    = list(set(os.getenv('PSQL_DB').split(',')))[0]
PSQL_USER  = os.getenv('PSQL_USER', None)
PSQL_PSSWD = os.getenv('PSQL_PWSD', None)


DATABASE_URL = (
    "postgresql+psycopg2://"
    f"{PSQL_USER}:{PSQL_PSSWD}@{PSQL_HOST}:{PSQL_PORT}/{PSQL_DB}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

session_local = sessionmaker(
    bind       = engine,
    autoflush  = False,
    autocommit = False,
)


def get_db() -> Generator[Session, None, None]:
    db = session_local()

    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""

    pass


class FileDesc(Base):
    """Metadata describing a stored file."""

    __tablename__ = FD_TABLE

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Original filename supplied by the user.
    filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # File properties
    # ------------------------------------------------------------------

    size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    content_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    extension: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    # Optional checksum for detecting duplicate/corrupted files.
    checksum: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    # Where the actual file is stored.
    #
    # Examples:
    #   /data/uploads/...
    #   s3://bucket/...
    #   oss://bucket/...
    storage_uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Timestamps
    # ------------------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


from pydantic import BaseModel

class FileCreate(BaseModel):
    filename: str
    size: int
    content_type: str | None = None
    checksum: str | None = None
    storage_uri: str


class FileUpdate(BaseModel):
    filename: str | None = None
    checksum: str | None = None


class FileRead(BaseModel):
    id: UUID
    filename: str
    size: int
    content_type: str | None
    checksum: str | None
    storage_uri: str
    created_at: datetime
    modified_at: datetime | None

    model_config = {
        "from_attributes": True
    }

# repositories/file.py
from uuid import UUID

from sqlalchemy     import select
from sqlalchemy.orm import Session


class FileRepository:

    def create(
        self,
        db   : Session,
        data : FileCreate,
    ) -> FileDesc:

        fd = FileDesc(
            filename     = data.filename,
            size         = data.size,
            content_type = data.content_type,
            checksum     = data.checksum,
            storage_uri  = data.storage_uri,
        )

        db.add(fd)
        db.commit()
        db.refresh(fd)

        return fd

    def get(
        self,
        db      : Session,
        file_id : UUID,
    ) -> FileDesc | None:

        stmt = select(FileDesc).where(
            FileDesc.id == file_id
        )

        return db.scalar(stmt)

    def list(
        self,
        db : Session,
    ) -> list[FileDesc]:

        stmt = select(FileDesc).order_by(
            FileDesc.created_at.desc()
        )

        return list(db.scalars(stmt))

    def update(
        self,
        db   : Session,
        file : FileDesc,
        data : FileUpdate,
    ) -> FileDesc:

        if data.filename is not None:
            file.filename = data.filename

        if data.checksum is not None:
            file.checksum = data.checksum

        db.commit()
        db.refresh(file)

        return file

    def delete(
        self,
        db   : Session,
        file : FileDesc,
    ) -> None:

        db.delete(file)
        db.commit()