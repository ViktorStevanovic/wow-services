from enum import StrEnum


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"


class ComponentStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
