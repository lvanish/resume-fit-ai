"""Deterministic checks on extracted profiles.

These checks reject empty or ungrounded output. They do not fill missing fields.
"""

from __future__ import annotations

import re

from app.models.candidate_profile import CandidateProfile
from app.models.job_profile import JobProfile
from app.services.llm_service import ExtractionValidationError

_PLACEHOLDER = re.compile(
    r"^(?:none|n/?a|na|unknown|null|not specified|not available|"
    r"no preferred skills?|none specified(?:\b.*)?|no responsibilities|-+)$",
    re.IGNORECASE,
)
_OBVIOUS_ROLE = re.compile(
    r"\b(?:full[- ]stack engineer|software engineer|backend engineer|frontend engineer|"
    r"system engineer|technical intern|relationship manager)\b",
    re.IGNORECASE,
)
_INDUSTRY_LINE = re.compile(r"industry\s*:\s*([^\n]+)", re.IGNORECASE)
_EMPLOYMENT_LINE = re.compile(r"employment type\s*:\s*([^\n]+)", re.IGNORECASE)


def validate_candidate_profile(profile: CandidateProfile, source: str) -> CandidateProfile:
    """Reject an empty, placeholder, or ungrounded candidate profile."""
    _require_string_list("Candidate responsibilities", profile.responsibilities)
    _reject_placeholder("Candidate role", profile.role)
    _reject_placeholder_items("Candidate skills", profile.skills)
    _reject_placeholder_items("Candidate responsibilities", profile.responsibilities)
    if _obvious_role(source) and not _present(profile.role):
        raise ExtractionValidationError(
            "Candidate role is empty, but the resume states a role."
        )
    if _present(profile.role) and not _role_grounded(profile.role, source):
        raise ExtractionValidationError(
            f"Candidate role '{profile.role}' does not appear in the resume."
        )
    for skill in profile.skills:
        if not validate_skill_against_source(skill, source):
            raise ExtractionValidationError(
                f"Candidate skill '{skill}' does not appear in the resume."
            )
    _require_grounded_responsibilities("Candidate responsibility", profile.responsibilities, source)
    profile = profile.model_copy(
        update={
            "skills": _unique(profile.skills),
            "responsibilities": _unique(profile.responsibilities),
        }
    )
    if _profile_is_empty(profile.role, profile.skills, profile.responsibilities, profile.years_of_experience):
        raise ExtractionValidationError("The model returned an empty candidate profile.")
    return profile


def validate_job_profile(profile: JobProfile, source: str) -> JobProfile:
    """Reject an empty, placeholder, or ungrounded job profile."""
    _require_string_list("Job required skills", profile.required_skills)
    _require_string_list("Job preferred skills", profile.preferred_skills)
    _require_string_list("Job responsibilities", profile.responsibilities)
    _reject_placeholder("Job role", profile.role)
    _reject_placeholder_items("Job required skills", profile.required_skills)
    _reject_placeholder_items("Job preferred skills", profile.preferred_skills)
    _reject_placeholder_items("Job responsibilities", profile.responsibilities)
    if _obvious_role(source) and not _present(profile.role):
        raise ExtractionValidationError(
            "Job role is empty, but the job description states a role."
        )
    profile = profile.model_copy(update={"role": _advertised_role(profile.role, source)})
    if _present(profile.role) and not _role_grounded(profile.role, source):
        raise ExtractionValidationError(
            f"Job role '{profile.role}' does not appear in the job description."
        )
    blocked = _label_only_phrases(source)
    for skill in [*profile.required_skills, *profile.preferred_skills]:
        if _norm(skill) in blocked:
            raise ExtractionValidationError(
                f"Job skill '{skill}' repeats an industry or employment label, not a listed skill."
            )
        if not validate_skill_against_source(skill, source):
            raise ExtractionValidationError(
                f"Job skill '{skill}' does not appear in the job description."
            )
    _require_grounded_responsibilities("Job responsibility", profile.responsibilities, source)
    profile = profile.model_copy(
        update={
            "required_skills": _unique(profile.required_skills),
            "preferred_skills": _unique(profile.preferred_skills),
            "responsibilities": _unique(profile.responsibilities),
        }
    )
    if _profile_is_empty(
        profile.role,
        profile.required_skills,
        profile.responsibilities,
        profile.minimum_years_experience,
    ) and not profile.preferred_skills:
        raise ExtractionValidationError("The model returned an empty job profile.")
    return profile


def _require_string_list(label: str, values: object) -> None:
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ExtractionValidationError(f"{label} must be a list of strings.")


def _reject_placeholder(label: str, value: str | None) -> None:
    if value is not None and _is_placeholder(value):
        raise ExtractionValidationError(f"{label} contains a placeholder value.")


def _reject_placeholder_items(label: str, values: list[str]) -> None:
    for value in values:
        if _is_placeholder(value) or not value.strip():
            raise ExtractionValidationError(f"{label} contains a placeholder value.")


def _is_placeholder(value: str) -> bool:
    return _PLACEHOLDER.match(value.strip()) is not None


def _obvious_role(source: str) -> bool:
    return _OBVIOUS_ROLE.search(source) is not None


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        key = _norm(value)
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return unique


def _present(value: str | None) -> bool:
    return bool(value and value.strip()) and not _is_placeholder(value)


def _profile_is_empty(role: str | None, skills: list[str], responsibilities: list[str], years: float | None) -> bool:
    return not _present(role) and not skills and not responsibilities and years is None


_QUOTE_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
        "\u2215": "/",
    }
)
_SKILL_TOKEN = re.compile(r"[a-z0-9]+(?:\+\+|#)?(?:\.[a-z0-9]+)*")
_GLUED_WORD = re.compile(r"[A-Za-z][A-Za-z0-9.+#]*")
# These stay one token. CamelCase splitting would turn JavaScript into Java + Script.
_ATOMIC_SKILL_TOKENS = frozenset(
    {
        "javascript",
        "typescript",
        "postgresql",
        "mongodb",
        "graphql",
        "nodejs",
        "nextjs",
        "expressjs",
        "oauth",
    }
)
_SKILL_ALIAS_GROUPS = (
    ("spring boot", "spring boot 3", "springboot"),
    ("react", "react.js", "reactjs", "react js"),
    ("node.js", "nodejs", "node js"),
    ("postgresql", "postgres"),
    ("javascript", "js"),
)


def _split_glued_words(value: str) -> str:
    """Split portal text that joins skills at a capital letter, such as UpsellingTarget.

    JavaScript and the other atomic names stay one token, so Java does not match them.
    """

    def split_word(match: re.Match[str]) -> str:
        word = match.group(0)
        folded = re.sub(r"[^a-z0-9]", "", word.casefold())
        if folded in _ATOMIC_SKILL_TOKENS:
            return word
        return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", word)

    return _GLUED_WORD.sub(split_word, value)


def _skill_tokens(value: str) -> tuple[str, ...]:
    text = _split_glued_words(value).translate(_QUOTE_TRANSLATION).casefold()
    return tuple(_SKILL_TOKEN.findall(text))


_SKILL_ALIAS_TOKENS = tuple(
    tuple(tuple(_skill_tokens(name)) for name in group) for group in _SKILL_ALIAS_GROUPS
)


def validate_skill_against_source(extracted_skill: str, source_text: str) -> bool:
    """Return whether a normalized skill is grounded in raw source text.

    Slash, parentheses, and other punctuation separate tokens. A capital letter
    also separates skills that a job board pasted together, such as
    UpsellingTarget. Explicit alias groups are the only equivalences. JavaScript
    stays one token, so Java does not match it.
    """
    tokens = _skill_tokens(extracted_skill)
    if not tokens:
        return False
    source_tokens = _skill_tokens(source_text)
    return any(_token_sequence(form, source_tokens) for form in _alias_forms(tokens))


def _alias_forms(tokens: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    for group in _SKILL_ALIAS_TOKENS:
        if tokens in group:
            return group
    return (tokens,)


def _token_sequence(needle: tuple[str, ...], haystack: tuple[str, ...]) -> bool:
    width = len(needle)
    if width == 0 or width > len(haystack):
        return False
    return any(haystack[start : start + width] == needle for start in range(len(haystack) - width + 1))


def _grounded(value: str, source: str) -> bool:
    source_norm = _norm(source)
    parts = [part for part in (_norm(piece) for piece in re.split(r"[,/]|\band\b", value)) if part]
    if not parts:
        return False
    return all(_appears(part, source_norm) for part in parts)


def _require_grounded_responsibilities(label: str, values: list[str], source: str) -> None:
    source_norm = _excerpt_norm(source)
    for value in values:
        if _excerpt_norm(value) not in source_norm:
            raise ExtractionValidationError(
                f"{label} '{value}' does not appear in the source text."
            )


def _advertised_role(role: str | None, source: str) -> str | None:
    """Prefer the posting's first-line title when the model shortens or extends it."""
    if not _present(role):
        return role
    first = next((line.strip() for line in source.splitlines() if line.strip()), "")
    if not first or len(first) > 80 or any(mark in first for mark in ".?!"):
        return role
    if _excerpt_norm(first) == _excerpt_norm(role):
        return role
    first_words = _excerpt_norm(first).split()
    role_words = _excerpt_norm(role).split()
    if len(first_words) < 2 or len(role_words) < 2:
        return role
    if _words_in_order(role_words, first_words) or _words_in_order(first_words, role_words):
        return first
    return role


def _role_grounded(role: str, source: str) -> bool:
    """Accept a title that is written in the source, including light normalization.

    One extra word may sit between title words, so "Full-stack engineer" still
    matches "Full-Stack Software Engineer". Skills do not use this rule.
    """
    if _grounded(role, source):
        return True
    return _words_in_order(_excerpt_norm(role).split(), _excerpt_norm(source).split())


def _words_in_order(needles: list[str], haystack: list[str]) -> bool:
    if not needles:
        return False
    start = 0
    for index, word in enumerate(needles):
        limit = len(haystack) if index == 0 else min(len(haystack), start + 2)
        found = next((pos for pos in range(start, limit) if haystack[pos] == word), None)
        if found is None:
            return False
        start = found + 1
    return True


def _appears(part: str, source_norm: str) -> bool:
    if len(part) <= 3:
        return re.search(rf"(?<![a-z0-9]){re.escape(part)}(?![a-z0-9])", source_norm) is not None
    return part in source_norm


def _label_only_phrases(source: str) -> set[str]:
    labels: set[str] = set()
    for pattern in (_INDUSTRY_LINE, _EMPLOYMENT_LINE):
        for match in pattern.finditer(source):
            for piece in re.split(r"[,/]|\band\b", match.group(1)):
                norm = _norm(piece)
                if not norm:
                    continue
                without = pattern.sub(" ", source)
                if not _appears(norm, _norm(without)):
                    labels.add(norm)
    return labels


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _excerpt_norm(value: str) -> str:
    """Case, whitespace, quotes, and punctuation folded for contiguous excerpt checks."""
    text = value.translate(_QUOTE_TRANSLATION).casefold()
    text = text.replace("_", " ")
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()
