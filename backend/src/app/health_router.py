from fastapi import APIRouter

from src.shared.enums.health_status import HealthStatus
from src.shared.types.health_response import HealthResponse

router = APIRouter()


@router.get("/health")
def read_health() -> HealthResponse:
    return HealthResponse(status=HealthStatus.OK)
