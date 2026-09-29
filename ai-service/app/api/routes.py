from fastapi import APIRouter, Depends

from app.config import get_settings
from app.models.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.laya_service import LayaService

router = APIRouter(prefix="/api/v1")


def get_laya_service() -> LayaService:
    return LayaService(get_settings())


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    request: AnalyzeRequest,
    laya_service: LayaService = Depends(get_laya_service),
) -> AnalyzeResponse:
    score = laya_service.calculate_match_score(request.resume, request.job_description)
    return AnalyzeResponse(score=score)
