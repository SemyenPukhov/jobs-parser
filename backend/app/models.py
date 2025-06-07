from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid
from uuid import UUID


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
