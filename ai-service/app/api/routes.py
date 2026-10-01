from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.match_scoring import public_match_score

router = APIRouter(prefix="/api/v1")


def get_match_settings() -> Settings:
    return get_settings()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    request: AnalyzeRequest,
    settings: Settings = Depends(get_match_settings),
) -> AnalyzeResponse:
    score = public_match_score(settings, request.resume, request.job_description)
    return AnalyzeResponse(score=score)
