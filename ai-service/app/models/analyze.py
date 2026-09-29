from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    resume: str
    job_description: str = Field(alias="jobDescription")

    @field_validator("resume", "job_description")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class AnalyzeResponse(BaseModel):
    score: int = Field(ge=0, le=100)


class ErrorResponse(BaseModel):
    code: str
    message: str
