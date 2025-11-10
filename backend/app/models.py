from sqlmodel import SQLModel, Field, Relationship, Column
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, EmailStr
from sqlalchemy import JSON


class JobProcessingStatusEnum(str, Enum):
    APPLIED = "Applied"
    NOT_SUITABLE = "NotSuitable"


class JobProcessingStatus(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: UUID = Field(foreign_key="job.id", unique=True, nullable=False)
    user_id: UUID = Field(foreign_key="user.id", nullable=False)
    status: JobProcessingStatusEnum
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    job: Optional["Job"] = Relationship(back_populates="processing_status")
    user: Optional["User"] = Relationship(back_populates="processed_jobs")


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
    matching_results: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON))

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
    matching_results: Optional[Dict[str, Any]]
    processing_status: Optional[JobProcessingStatusRead]

    class Config:
        orm_mode = True


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: EmailStr = Field(unique=True, index=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    processed_jobs: List[JobProcessingStatus] = Relationship(back_populates="user")


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
