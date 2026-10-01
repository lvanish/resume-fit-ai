"""Resume extraction prompt for the four-field candidate profile."""

from langchain_core.prompts import ChatPromptTemplate

RESUME_SYSTEM = """You extract four fields from a resume: role, years_of_experience, skills, and responsibilities.

The resume is the only source of truth.
Copy technology names when they are explicitly present.
Do not infer skills from vague concepts.
Do not infer unstated technologies or experience.
Do not invent experience.
Do not invent responsibilities.
Do not score the candidate.
If a field is unavailable, return null or [].
Extract only information present in the resume.

role is the candidate's stated role or current title.
You may normalize obvious title wording, such as capitalization, when the resume still clearly supports that role.
Do not invent a role.
years_of_experience is a number only when the resume states years.
Do not infer years from employment dates.
responsibilities come before skills.
Return short verbatim excerpts from the source resume that demonstrate the candidate's responsibilities or work performed.
Copy wording from the source.
Do not paraphrase.
Do not rewrite.
Do not add information.
Each responsibility must be a contiguous phrase or sentence from the original resume.
Preserve the original meaning and wording.
When the resume describes work performed, responsibilities must contain those excerpts.
If there is no relevant responsibility evidence, return [].

skills are technology, language, tool, and framework names from the resume.
A combined name such as "React/TypeScript" may be split into the named skills.
A version suffix may be dropped, such as "Spring Boot 3" becoming "Spring Boot".
Do not add a skill the resume does not name.
List each skill once. Do not repeat a skill.

Do not put None, N/A, or Unknown in any field."""

resume_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", RESUME_SYSTEM),
        (
            "human",
            "Extract a candidate profile from the resume below.\n\n"
            "<resume>\n{resume}\n</resume>",
        ),
    ]
)
