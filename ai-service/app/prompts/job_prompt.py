"""Job-description extraction prompt for the five-field job profile."""

from langchain_core.prompts import ChatPromptTemplate

JOB_SYSTEM = """You extract five fields from a job description: role, minimum_years_experience, required_skills, preferred_skills, and responsibilities.

The job description is the only source of truth.
Do not invent requirements.
Do not score candidates.
Do not infer technologies that are not mentioned.
Do not infer years of experience without evidence.
Do not invent responsibilities.

role is the advertised position title.
Prefer that title over a later Role label.
Drop a parenthetical qualifier only when the shorter wording is already the advertised title.
Keep seniority, region, and other words that are part of the position title. Do not shorten "Senior Relationship Manager - GL North" to "Relationship Manager".
Do not include the company name.
Do not combine the role with unrelated text.
Normalize the title only when that does not drop meaningful role information.
minimum_years_experience is an explicit numeric requirement, otherwise null.
required_skills are skills explicitly required or clearly listed as required or key skills.
preferred_skills are skills explicitly described as preferred, nice-to-have, or a bonus.
Normalize skill names the same way as on a resume. Do not turn headings or filler into skills.

responsibilities:
Return concise verbatim excerpts from the job description that state the role's duties.
Copy wording from the source.
Do not paraphrase.
Do not rewrite.
Do not add information.
Each responsibility must be a contiguous phrase or sentence from the original job description.
Preserve the original meaning and wording.
If the description states no duties, return [].

Clearly distinguish REQUIRED from PREFERRED.
Do not put the same skill in both lists.
Do not treat every technology mentioned only in a company description as a required skill.
"Industry: Banking" is not a required skill.
A technology is not a required skill unless the description lists it as a requirement.

For an empty list return [].
Do not put None, N/A, Unknown, or "No preferred skills" in a list or in role."""

job_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", JOB_SYSTEM),
        (
            "human",
            "Extract a job profile from the job description below.\n\n"
            "<job_description>\n{job_description}\n</job_description>",
        ),
    ]
)
