from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class DemoUser(SQLModel, table=True):
    """A prospect who requested a demo. Password stays NULL until they set it."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    business: str
    business_type: str = "Restaurant"
    message: str = ""
    email: str = Field(index=True, unique=True)
    password: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DashState(SQLModel, table=True):
    """Per-user dashboard settings (custom safe ranges, acknowledged alerts) as JSON."""
    user_id: int = Field(primary_key=True, foreign_key="demouser.id")
    data: str = "{}"


class Reading(SQLModel, table=True):
    """One temperature reading sent by a sensor / app / script."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="demouser.id", index=True)
    sensor: str
    temperature: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
