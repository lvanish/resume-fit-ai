"""Extractive compaction so a resume and job description fit the Laya context.

No text is generated. Sections are kept, dropped, or cut on token boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.token_utils import (
    count_tokens,
    truncate_suffix_to_tokens,
    truncate_to_tokens,
)

OMISSION_MARKER = "[section content omitted due to model input limit]"
_RESUME_SHARE = 0.55

_RESUME_ALIASES: tuple[tuple[str, str], ...] = (
    ("professional summary", "summary"),
    ("professional experience", "experience"),
    ("work experience", "experience"),
    ("technical skills", "skills"),
    ("certifications", "certifications"),
    ("achievements", "certifications"),
    ("employment", "experience"),
    ("experience", "experience"),
    ("summary", "summary"),
    ("objective", "summary"),
    ("education", "education"),
    ("projects", "projects"),
    ("project", "projects"),
    ("skills", "skills"),
    ("languages", "other"),
)

_JD_ALIASES: tuple[tuple[str, str], ...] = (
    ("required qualifications", "qualifications"),
    ("minimum qualifications", "qualifications"),
    ("preferred qualifications", "preferred"),
    ("what you will do", "responsibilities"),
    ("what you'll do", "responsibilities"),
    ("required skills", "requirements"),
    ("preferred skills", "preferred"),
    ("about the company", "other"),
    ("about the position", "role"),
    ("about the role", "role"),
    ("who we are", "other"),
    ("about us", "other"),
    ("qualifications", "qualifications"),
    ("requirements", "requirements"),
    ("responsibilities", "responsibilities"),
    ("nice to have", "preferred"),
    ("must have", "requirements"),
    ("bonus", "preferred"),
)

_RESUME_PRIORITY = {
    "summary": 0,
    "skills": 1,
    "experience": 2,
    "projects": 3,
    "education": 4,
    "certifications": 5,
    "other": 6,
    "body": 2,
}
_JD_PRIORITY = {
    "role": 0,
    "requirements": 1,
    "qualifications": 2,
    "responsibilities": 3,
    "preferred": 4,
    "other": 5,
    "body": 1,
}


@dataclass(frozen=True)
class Section:
    category: str
    heading: str
    body: str

    @property
    def text(self) -> str:
        if self.heading and self.body:
            return f"{self.heading}\n{self.body}"
        return self.heading or self.body


@dataclass(frozen=True)
class PreparedInput:
    resume: str
    job_description: str
    original_resume_tokens: int
    original_job_description_tokens: int
    final_resume_tokens: int
    final_job_description_tokens: int

    @property
    def compacted(self) -> bool:
        return (
            self.final_resume_tokens < self.original_resume_tokens
            or self.final_job_description_tokens < self.original_job_description_tokens
        )


class InputPreprocessor:
    def prepare_for_laya(
        self,
        resume: str,
        job_description: str,
        tokenizer,
        content_budget: int,
        state_limit: int | None = None,
        measure_state=None,
    ) -> PreparedInput:
        if content_budget < 1:
            raise ValueError("content_budget must be positive")
        original_resume_tokens = count_tokens(resume, tokenizer)
        original_job_tokens = count_tokens(job_description, tokenizer)
        budget = content_budget
        prepared = self._fit(resume, job_description, tokenizer, budget, original_resume_tokens, original_job_tokens)
        if measure_state is None or state_limit is None:
            return prepared

        for _ in range(8):
            state_tokens = measure_state(prepared.resume, prepared.job_description)
            if state_tokens <= state_limit:
                return prepared
            overflow = state_tokens - state_limit
            budget -= overflow + 4
            if budget < 1:
                break
            prepared = self._fit(
                resume,
                job_description,
                tokenizer,
                budget,
                original_resume_tokens,
                original_job_tokens,
            )
        state_tokens = measure_state(prepared.resume, prepared.job_description)
        if state_tokens > state_limit:
            raise ValueError(
                "Preprocessing could not fit the resume and job description into the Laya context limit."
            )
        return prepared

    def _fit(
        self,
        resume: str,
        job_description: str,
        tokenizer,
        content_budget: int,
        original_resume_tokens: int,
        original_job_tokens: int,
    ) -> PreparedInput:
        resume_alloc, job_alloc = allocate_budget(
            content_budget,
            original_resume_tokens,
            original_job_tokens,
        )
        resume_text = compact_document(
            resume,
            resume_alloc,
            tokenizer,
            aliases=_RESUME_ALIASES,
            priorities=_RESUME_PRIORITY,
            preamble_category="summary",
            whole_category="body",
        )
        job_text = compact_document(
            job_description,
            job_alloc,
            tokenizer,
            aliases=_JD_ALIASES,
            priorities=_JD_PRIORITY,
            preamble_category="role",
            whole_category="body",
        )
        return PreparedInput(
            resume=resume_text,
            job_description=job_text,
            original_resume_tokens=original_resume_tokens,
            original_job_description_tokens=original_job_tokens,
            final_resume_tokens=count_tokens(resume_text, tokenizer),
            final_job_description_tokens=count_tokens(job_text, tokenizer),
        )


def allocate_budget(total: int, resume_tokens: int, job_tokens: int) -> tuple[int, int]:
    """Split `total` about 55/45, giving unused room to the longer document."""
    if total < 1:
        return 0, 0
    if resume_tokens + job_tokens <= total:
        return resume_tokens, job_tokens
    resume_share = int(total * _RESUME_SHARE)
    job_share = total - resume_share
    if resume_tokens <= resume_share:
        return resume_tokens, total - resume_tokens
    if job_tokens <= job_share:
        return total - job_tokens, job_tokens
    return resume_share, job_share


def detect_resume_sections(text: str) -> list[Section]:
    return _detect_sections(text, _RESUME_ALIASES, preamble_category="summary", whole_category="body")


def detect_job_sections(text: str) -> list[Section]:
    return _detect_sections(text, _JD_ALIASES, preamble_category="role", whole_category="body")


def compact_document(
    text: str,
    token_budget: int,
    tokenizer,
    *,
    aliases: tuple[tuple[str, str], ...],
    priorities: dict[str, int],
    preamble_category: str,
    whole_category: str,
) -> str:
    if token_budget <= 0:
        return ""
    if count_tokens(text, tokenizer) <= token_budget:
        return text

    sections = _detect_sections(
        text,
        aliases,
        preamble_category=preamble_category,
        whole_category=whole_category,
    )
    rendered = [section.text for section in sections if section.text.strip()]
    if not rendered:
        return ""
    counts = [count_tokens(piece, tokenizer) for piece in rendered]
    if sum(counts) <= token_budget:
        return text

    order = sorted(
        range(len(rendered)),
        key=lambda index: (priorities.get(sections[index].category, priorities.get("other", 99)), index),
    )
    allocations = [0] * len(rendered)
    remaining = token_budget
    for index in order:
        if remaining <= 0:
            break
        grant = min(counts[index], remaining)
        allocations[index] = grant
        remaining -= grant

    def render(index: int) -> str:
        allocation = allocations[index]
        if allocation <= 0:
            return ""
        piece = rendered[index]
        if count_tokens(piece, tokenizer) <= allocation:
            return piece
        return fit_section(piece, allocation, tokenizer)

    parts = [render(index) for index in range(len(rendered))]

    def joined() -> str:
        return "\n\n".join(part for part in parts if part.strip())

    # Separators between kept sections can push the total over the budget.
    # Remove that overflow from the lowest-priority section, not from the
    # start of the whole document.
    lowest_first = sorted(
        range(len(rendered)),
        key=lambda index: (
            -priorities.get(sections[index].category, priorities.get("other", 99)),
            -index,
        ),
    )
    for _ in range(12):
        compacted = joined()
        overflow = count_tokens(compacted, tokenizer) - token_budget
        if overflow <= 0:
            return compacted
        for index in lowest_first:
            if allocations[index] <= 0:
                continue
            allocations[index] = max(0, allocations[index] - overflow)
            parts[index] = render(index)
            break
        else:
            break
    compacted = joined()
    if count_tokens(compacted, tokenizer) <= token_budget:
        return compacted
    return truncate_to_tokens(compacted, token_budget, tokenizer)


def fit_section(text: str, max_tokens: int, tokenizer) -> str:
    """Keep a section inside `max_tokens`, preferring its beginning and end."""
    if max_tokens <= 0:
        return ""
    if count_tokens(text, tokenizer) <= max_tokens:
        return text

    prefix = truncate_to_tokens(text, max_tokens, tokenizer)
    marker = f"\n{OMISSION_MARKER}\n"
    marker_tokens = count_tokens(marker, tokenizer)
    if marker_tokens + 2 >= max_tokens:
        return prefix

    content_budget = max_tokens - marker_tokens
    target_head = max(1, (content_budget * 2) // 3)
    head = truncate_to_tokens(text, target_head, tokenizer)
    while head and count_tokens(head + marker, tokenizer) >= max_tokens:
        head = truncate_to_tokens(head, count_tokens(head, tokenizer) - 1, tokenizer)
    if not head:
        return prefix

    low = 0
    high = len(text)
    best_tail = ""
    while low <= high:
        mid = (low + high) // 2
        tail = text[-mid:] if mid else ""
        if tail and len(head) + len(tail) >= len(text):
            high = mid - 1
            continue
        candidate = head + marker + tail if tail else head
        if count_tokens(candidate, tokenizer) <= max_tokens:
            best_tail = tail
            low = mid + 1
        else:
            high = mid - 1
    if not best_tail:
        return prefix
    return head + marker + best_tail


def _detect_sections(
    text: str,
    aliases: tuple[tuple[str, str], ...],
    *,
    preamble_category: str,
    whole_category: str,
) -> list[Section]:
    alias_map = _alias_map(aliases)
    sections: list[Section] = []
    heading = ""
    category = preamble_category
    body: list[str] = []
    found_heading = False

    def flush() -> None:
        content = "\n".join(body).strip()
        if heading or content:
            sections.append(Section(category, heading, content))

    for line in text.splitlines():
        matched = _match_heading(line, alias_map)
        if matched is None:
            body.append(line)
            continue
        found_heading = True
        flush()
        heading = line.strip()
        category = matched
        body = []
    flush()
    if not found_heading:
        stripped = text.strip()
        if not stripped:
            return []
        return [Section(whole_category, "", stripped)]
    return [section for section in sections if section.text.strip()]


def _alias_map(aliases: tuple[tuple[str, str], ...]) -> dict[str, str]:
    ordered = sorted(aliases, key=lambda item: len(item[0]), reverse=True)
    return {name: category for name, category in ordered}


def _match_heading(line: str, alias_map: dict[str, str]) -> str | None:
    if len(line.strip()) > 80:
        return None
    normalized = _normalize_heading(line)
    if not normalized or len(normalized.split()) > 8:
        return None
    return alias_map.get(normalized)


def _normalize_heading(line: str) -> str:
    text = line.strip()
    text = re.sub(r"^[#>*\-\s]+", "", text)
    text = text.strip()
    text = text.strip(":-–—|")
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text.casefold()
