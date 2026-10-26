from app.core.schemas import BaseSchema
from app.features.health.enums import ComponentStatus, HealthStatus


class HealthRead(BaseSchema):
    status: HealthStatus
    database: ComponentStatus
