from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SERVICES = ("gateway", "reservation", "worker", "database")


class LogEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: datetime
    service: Literal["gateway", "reservation", "worker", "database"]
    level: Literal["INFO", "WARN", "ERROR"]
    message: str = Field(min_length=1, max_length=2000)
    latency_ms: float = Field(ge=0, le=3_600_000, allow_inf_nan=False)

    @field_validator("timestamp")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class LogWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[LogEvent] = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def bounded_window(self):
        stamps = [e.timestamp for e in self.events]
        if (max(stamps) - min(stamps)).total_seconds() > 60:
            raise ValueError("One analysis window must span at most 60 seconds")
        return self
