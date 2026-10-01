"""One explicit job requirement derived from a JobProfile."""

from enum import Enum

from pydantic import BaseModel, Field


class RequirementCategory(str, Enum):
    REQUIRED_SKILL = "REQUIRED_SKILL"
    PREFERRED_SKILL = "PREFERRED_SKILL"
    RESPONSIBILITY = "RESPONSIBILITY"
    EXPERIENCE = "EXPERIENCE"
    ROLE = "ROLE"


class Requirement(BaseModel):
    """A single named requirement. Matching is not performed here."""

    name: str = Field(description="Requirement text copied from the job profile.")
    category: RequirementCategory
