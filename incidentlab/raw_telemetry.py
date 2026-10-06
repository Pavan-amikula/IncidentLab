"""Bounded incremental ingestion of the explicit native request-event schema."""
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SERVICES = ('frontend', 'checkout', 'inventory')


class RequestEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_schema: Literal['incidentlab-http-v1'] = Field(alias='schema')
    service: Literal['frontend', 'checkout', 'inventory']
    trace_id: str = Field(pattern=r'^[0-9a-f]{32}$')
    span_id: str = Field(pattern=r'^[0-9a-f]{32}$')
    parent_span_id: str | None = Field(default=None, pattern=r'^[0-9a-f]{32}$')
    start: float = Field(gt=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    duration_ms: float = Field(ge=0, le=600000, allow_inf_nan=False)
    status: int = Field(ge=100, le=599)
    active_requests: int = Field(ge=1, le=10000)
    message: str = Field(max_length=2000)
    dependency: Literal['checkout', 'inventory'] | None = None
    dependency_status: int | None = Field(default=None, ge=0, le=599)

    @model_validator(mode='after')
    def coherent(self):
        if self.end < self.start:
            raise ValueError('Completion precedes request start')
        if abs((self.end-self.start)*1000-self.duration_ms) > 5:
            raise ValueError('Duration does not match measured wall-clock timestamps')
        return self


class EventCollector:
    def __init__(self, directory: Path):
        self.directory = directory
        self.positions = {service:0 for service in SERVICES}
        self.carry = {service:b'' for service in SERVICES}
        self.pending = []
        self.record_count = self.late_count = 0
        self.last_end = None

    def read_window(self, start, end):
        if end <= start or (self.last_end is not None and start < self.last_end):
            raise ValueError('Windows must be chronological and nonoverlapping')
        for service in SERVICES:
            path = self.directory/f'{service}.jsonl'
            if not path.exists():
                continue
            if path.stat().st_size < self.positions[service]:
                raise ValueError('Telemetry file was truncated; start a new collector')
            with path.open('rb') as source:
                source.seek(self.positions[service])
                chunk = source.read(4*1024*1024)
                self.positions[service] += len(chunk)
                if len(chunk) == 4*1024*1024 and source.read(1):
                    raise ValueError('Collector throughput capacity exceeded; stop rather than silently skip')
            lines = (self.carry[service]+chunk).split(b'\n')
            self.carry[service] = lines.pop()
            if len(self.carry[service]) > 65536:
                raise ValueError('Telemetry record exceeds the bounded framing size')
            for line in lines:
                if not line:
                    continue
                record = RequestEvent.model_validate_json(line).model_dump(by_alias=True)
                if record['service'] != service:
                    raise ValueError('Source service does not match its event identity')
                self.pending.append(record)
                self.record_count += 1
        if len(self.pending) > 50000:
            raise ValueError('Pending telemetry capacity exceeded')
        current, future = [], []
        for record in self.pending:
            if record['end'] < start:
                self.late_count += 1
            elif record['end'] < end:
                current.append(record)
            else:
                future.append(record)
        self.pending = future
        self.last_end = end
        return current

    def audit(self):
        return dict(records_read=self.record_count, late_records=self.late_count,
                    pending_records=len(self.pending), partial_record_bytes=sum(map(len,self.carry.values())),
                    policy='Completed newline-framed events, incremental offsets, explicit late/capacity accounting')
