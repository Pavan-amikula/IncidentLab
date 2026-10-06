"""Synthetic observations. Evaluation labels never enter LogWindow/model inputs."""
import random
from datetime import datetime, timedelta, timezone

from .schema import LogEvent, LogWindow, SERVICES

SCENARIOS = ("healthy", "database_unavailable", "worker_failure", "database_slow", "traffic_surge", "missing_telemetry")
BASE_LATENCY = {"gateway": 25, "reservation": 18, "worker": 12, "database": 8}
HEALTHY_MESSAGE = {
    "gateway": "request completed status=200 request={}",
    "reservation": "reservation committed request={}",
    "worker": "job completed request={}",
    "database": "query completed request={}",
}


def make_window(seed: int, scenario: str = "healthy", step: int = 0) -> LogWindow:
    if scenario not in SCENARIOS:
        raise ValueError("Unknown scenario")
    rng = random.Random(seed)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=step * 5)
    events = []
    for service in SERVICES:
        if scenario == "missing_telemetry" and service in ("database", "worker"):
            continue
        count = rng.randint(8, 20)
        if scenario == "traffic_surge":
            count *= 4
        for i in range(count):
            latency = max(1, rng.gauss(BASE_LATENCY[service], 4))
            message = HEALTHY_MESSAGE[service].format(rng.randint(1000, 9999))
            level = "INFO"
            if scenario == "database_unavailable":
                if service == "database":
                    level, message, latency = "ERROR", "connection refused accepting clients", 1000
                elif service in ("reservation", "worker"):
                    level, message, latency = "ERROR", "upstream database connection timeout", 1100
                else:
                    level, message, latency = "ERROR", "upstream reservation request failed status=503", 1200
            elif scenario == "worker_failure":
                if service == "worker":
                    level, message = "ERROR", "worker process exited unexpectedly"
                elif service == "reservation":
                    level, message = "WARN", "job queue backlog exceeds threshold"
            elif scenario == "database_slow":
                if service == "database":
                    latency *= 50
                elif service in ("reservation", "gateway"):
                    latency *= 15
            events.append(LogEvent(timestamp=start + timedelta(milliseconds=i * 100),
                                   service=service, level=level, message=message,
                                   latency_ms=round(latency, 3)))
    return LogWindow(events=sorted(events, key=lambda e: e.timestamp))
