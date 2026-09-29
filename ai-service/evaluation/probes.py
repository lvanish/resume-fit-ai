"""Controlled synthetic pairs for behavioral checks.

These strings are fictional. They are not copied from real resumes.
"""

from __future__ import annotations

BACKEND_JD = """Backend Engineer
Requirements
Java, Spring Boot, PostgreSQL, and REST APIs are required.
At least 3 years of professional software experience.

Responsibilities
Design HTTP APIs, review code, and support production incidents.
Write automated tests for service changes.

Preferred Skills
Docker.
"""

SKILL_VERSIONS = {
    "A": """Professional Summary
Software engineer.
Technical Skills
Java
Work Experience
Built internal desktop utilities for 3 years.
""",
    "B": """Professional Summary
Software engineer.
Technical Skills
Java, Spring Boot
Work Experience
Built internal desktop utilities for 3 years and started a Spring Boot service.
""",
    "C": """Professional Summary
Software engineer.
Technical Skills
Java, Spring Boot, PostgreSQL, REST APIs
Work Experience
Built Spring Boot REST APIs backed by PostgreSQL for 3 years.
""",
}

EXPERIENCE_BODY = """Technical Skills
Java, Spring Boot, REST APIs, PostgreSQL
"""

EXPERIENCE_VERSIONS = {
    "A": EXPERIENCE_BODY
    + """Work Experience
Junior Software Engineer, 2024-present
- Assisted on a Spring Boot REST service and small PostgreSQL queries for about 1 year.
""",
    "B": EXPERIENCE_BODY
    + """Work Experience
Software Engineer, 2022-present
- Built Spring Boot REST APIs and PostgreSQL queries for 3 years.
""",
    "C": EXPERIENCE_BODY
    + """Professional Summary
Senior backend engineer with 6 years of experience.
Work Experience
Senior Software Engineer, 2019-present
- Led Spring Boot REST API design and PostgreSQL performance work for 6 years.
- Supported production incidents and mentored other engineers.
""",
}

RESPONSIBILITY_JD = """Backend Engineer
Requirements
Java and Spring Boot. 4 years of experience.

Responsibilities
Design APIs, review pull requests, respond to production incidents, and write automated tests.
"""

RESPONSIBILITY_VERSIONS = {
    "A": """Professional Summary
Java developer with 4 years of experience.
Technical Skills
Java, Spring Boot
Work Experience
Software Engineer, 2021-present
- Maintained internal batch scripts.
""",
    "B": """Professional Summary
Java developer with 4 years of experience.
Technical Skills
Java, Spring Boot
Work Experience
Software Engineer, 2021-present
- Built REST APIs in Spring Boot used by internal tools.
""",
    "C": """Professional Summary
Java developer with 4 years of experience.
Technical Skills
Java, Spring Boot, JUnit
Work Experience
Software Engineer, 2021-present
- Designed REST APIs and reviewed teammates' pull requests.
- Responded to production incidents and wrote automated JUnit tests.
""",
}

STRONG_BACKEND_RESUME = """Jordan Hale
Professional Summary
Backend engineer with 6 years building production Java services.
Technical Skills
Java, Spring Boot, REST APIs, PostgreSQL, Kafka, Docker
Work Experience
Senior Backend Engineer, Northline Payments, 2019-present
- Designed Spring Boot REST APIs and PostgreSQL schemas.
- Operated Kafka consumers for payment events.
"""

STRONG_BACKEND_JD = """Backend Engineer
Requirements
Java, Spring Boot, Kafka, and PostgreSQL. REST API experience. 4+ years.
Responsibilities
Design and operate backend services.
"""

FRONTEND_MISMATCH_RESUME = """Lina Ortiz
Professional Summary
Frontend developer.
Technical Skills
React, TypeScript, CSS
Work Experience
Frontend Engineer, Paperplane, 2021-present
- Built React screens and CSS layouts.
"""

REQUIREMENTS_JD = """Backend Engineer
Requirements
Java, Spring Boot, REST APIs, and PostgreSQL are required. 4+ years.
Responsibilities
Design APIs and improve database queries.
Preferred Skills
Docker.
"""

MARKETING = (
    "Join our innovative organization. We have a great culture, a fast-growing team, "
    "a meaningful mission, and values we repeat in every brochure. "
) * 40

MARKETING_JD = (
    REQUIREMENTS_JD
    + "\nAbout the company\n"
    + MARKETING
)

ORDER_A = """Professional Summary
Backend engineer with 5 years of Java service work.
Technical Skills
Java, Spring Boot, REST APIs, PostgreSQL
Work Experience
Software Engineer, Cedar Health, 2020-present
- Built Spring Boot REST APIs and PostgreSQL queries.
Education
B.S. Computer Science, 2020
"""

ORDER_B = """Education
B.S. Computer Science, 2020
Work Experience
Software Engineer, Cedar Health, 2020-present
- Built Spring Boot REST APIs and PostgreSQL queries.
Technical Skills
Java, Spring Boot, REST APIs, PostgreSQL
Professional Summary
Backend engineer with 5 years of Java service work.
"""

ORDER_JD = """Backend Engineer
Requirements
Java, Spring Boot, REST APIs, PostgreSQL. 4+ years.
Responsibilities
Build and maintain backend APIs.
"""

PARAPHRASE_A = """Professional Summary
Backend engineer with 4 years of experience.
Work Experience
Developed REST APIs using Java and Spring Boot.
Technical Skills
Java, Spring Boot, PostgreSQL
"""

PARAPHRASE_B = """Professional Summary
Backend engineer with 4 years of experience.
Work Experience
Built backend HTTP services with Spring Boot on the Java platform.
Technical Skills
Java, Spring Boot, PostgreSQL
"""

PARAPHRASE_JD = """Java Developer
Requirements
Java, Spring Boot, and REST APIs. PostgreSQL is required.
Responsibilities
Build backend HTTP services.
"""

NORMAL_RESUME = """Alex Rivera
Professional Summary
Backend engineer with 6 years of experience designing REST APIs and production Java services.
Technical Skills
Java, Spring Boot, REST APIs, PostgreSQL, Docker, JUnit
Work Experience
Senior Software Engineer, Northwind Payments, 2021-present
- Designed Spring Boot APIs used by billing services.
- Improved PostgreSQL queries.
Software Engineer, Harbor Logistics, 2018-2021
- Built REST services for shipment tracking.
Education
B.S. Computer Science, 2018
"""

NORMAL_JD = """Backend Engineer
About the Role
Build customer account APIs.
Requirements
5+ years of professional software experience.
Java, Spring Boot, REST APIs, and PostgreSQL.
Responsibilities
Design API changes and improve database performance.
Preferred Skills
Docker.
About the company
We build financial software and offer a collaborative engineering culture.
"""

LONG_RESUME = NORMAL_RESUME + "\nProjects\n" + (
    "Led a multi-quarter migration of billing workflows and coordinated releases with operations. " * 80
)
LONG_JD = NORMAL_JD + "\nAbout the company\n" + (
    "Our company has offices in many cities and a mission statement about culture, benefits, and community programs. "
    * 80
)

SHORT_RESUME = (
    "Software Engineer with 4 years of experience building backend services using "
    "Java, Spring Boot, REST APIs, PostgreSQL and Docker."
)
SHORT_JD = (
    "Backend Engineer. Requires Java, Spring Boot, REST APIs and PostgreSQL. Docker is preferred."
)
