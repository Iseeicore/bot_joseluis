from pydantic import BaseModel

from src.shared.enums.health_status import HealthStatus


class HealthResponse(BaseModel):
    status: HealthStatus
