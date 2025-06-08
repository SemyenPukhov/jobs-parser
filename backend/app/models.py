from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
import uuid
from uuid import UUID
from enum import Enum
from pydantic import BaseModel


class JobProcessingStatusEnum(str, Enum):
    APPLIED = "Applied"
    NOT_SUITABLE = "NotSuitable"


class JobProcessingStatus(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: UUID = Field(foreign_key="job.id", unique=True, nullable=False)
    status: JobProcessingStatusEnum
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    job: Optional["Job"] = Relationship(back_populates="processing_status")


class Job(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    url: str
    source: str
    description: Optional[str] = None
    company: Optional[str] = None
    company_url: Optional[str] = None
    apply_url: Optional[str] = None
    salary: Optional[str] = None
    parsed_at: datetime = Field(default_factory=datetime.utcnow)

    processing_status: Optional[JobProcessingStatus] = Relationship(
        back_populates="job")


class JobProcessingStatusRead(BaseModel):
    status: str
    comment: str
    created_at: datetime

    class Config:
        orm_mode = True


class JobRead(BaseModel):
    id: UUID
    title: str
    url: str
    source: str
    description: Optional[str]
    company: Optional[str]
    company_url: Optional[str]
    apply_url: Optional[str]
    salary: Optional[str]
    parsed_at: datetime
    processing_status: Optional[JobProcessingStatusRead]

    class Config:
        orm_mode = True
