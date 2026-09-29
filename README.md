# ResumeFit AI

ResumeFit AI compares a pasted resume with a pasted job description and returns a **Match Score** from 0 to 100.

The score describes how well the resume matches the job description according to ResumeFit's scoring methodology. It does not predict whether a company will interview the candidate.

## Current MVP scope

A user pastes a resume and a job description, then clicks **Analyze Match**. The request travels from React to Spring Boot to FastAPI. FastAPI asks Laya five ordinal score questions in one `Router.predict` call, then computes a weighted Match Score in application code.

Included:

- Single-page React UI
- `POST /api/v1/match` on Spring Boot
- `POST /api/v1/analyze` and `GET /health` on FastAPI
- Spring Boot health at `GET /actuator/health`
- Request validation and JSON error responses

Out of scope for this MVP:

- Resume recommendations or rewriting
- Authentication, accounts, history, or payments
- RAG, embeddings, vector databases, or external LLM APIs
- PDF or DOCX upload

## Architecture

```
React  →  Spring Boot  →  FastAPI  →  Laya  →  Match Score  →  Spring Boot  →  React
```

Spring Boot is the only API the browser calls. It forwards the resume and job description to the Python service with Spring's `RestClient`. FastAPI delegates scoring to `app/services/laya_service.py`. That module is the only place Laya-specific logic belongs.

A successful response is only the Match Score:

```json
{
  "score": 85
}
```

`score` is an integer from 0 to 100. It is a weighted combination of five Laya question scores. It is not an interview probability, and the API does not return the individual question scores.

## Technology stack

| Area | Stack |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Java 21, Spring Boot 4.1.1, Maven |
| AI service | Python 3.10+, FastAPI, Laya 0.3.21 (`typed-decisions`) |

## Project structure

```
resume-fit-ai/
├── frontend/          React UI
├── backend/           Spring Boot API
├── ai-service/        FastAPI service and Laya boundary
├── README.md
└── .gitignore
```

Backend layout:

- `controller` — `POST /api/v1/match`
- `service` — match use case
- `client` — HTTP client for the AI service
- `dto` — request and response records
- `exception` — global JSON error handling

AI service layout:

- `app/api` — HTTP routes and error mapping
- `app/models` — Pydantic request and response models
- `app/services/laya_service.py` — Laya integration boundary
- `app/config.py` — environment configuration

## Configuration

| Variable | Used by | Default |
| --- | --- | --- |
| `AI_SERVICE_URL` | Spring Boot | `http://localhost:8000` |
| `CORS_ALLOWED_ORIGINS` | Spring Boot | `http://localhost:5173` |
| `VITE_API_BASE_URL` | Frontend | empty; the Vite dev server proxies `/api` to port 8080 |
| `LAYA_MODEL` | AI service | `typed-decisions` |
| `LAYA_CHECKPOINT` | AI service | unset; optional Hugging Face revision |
| `LAYA_INPUT_TOKEN_BUDGET` | AI service | checkpoint state limit minus a 48-token safety margin |
| `AI_SERVICE_READ_TIMEOUT` | Spring Boot | `10m` (the first Laya request downloads the checkpoint) |

Do not commit `.env` files. Examples live in `frontend/.env.example` and `ai-service/.env.example`.

## How to run the frontend

From `resume-fit-ai/frontend`:

```powershell
npm install
npm run dev
```

Open http://localhost:5173.

## How to run Spring Boot

From `resume-fit-ai/backend` on Windows:

```powershell
.\mvnw.cmd spring-boot:run
```

On macOS or Linux:

```bash
./mvnw spring-boot:run
```

The API listens on http://localhost:8080. Health: http://localhost:8080/actuator/health.

To point at a different AI service:

```powershell
$env:AI_SERVICE_URL = "http://localhost:8000"
.\mvnw.cmd spring-boot:run
```

## How to run the Python AI service

From `resume-fit-ai/ai-service` on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health: http://localhost:8000/health.

Start the AI service before Spring Boot. The first scoring request downloads the `typed-decisions` checkpoint and can take several minutes. Later requests reuse the loaded model.

Run the scoring unit tests from `resume-fit-ai/ai-service`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run one real Laya pass:

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_laya
```

## Evaluation

The Match Score is a matching heuristic. It is not a prediction that someone will be interviewed or hired, and this MVP does not claim production-grade accuracy.

Evaluation is separate from the product API. The public response is still only `{ "score": N }`. A small synthetic dataset checks whether scores separate obvious match levels, and controlled pairs check for counterintuitive jumps. The cases are fictional. They are not copied from real people.

From `resume-fit-ai/ai-service`:

```powershell
.\.venv\Scripts\python.exe -m evaluation.run
```

`evaluation/dataset.json` holds at least 15 resume and job-description pairs. Each case has an id, the two texts, and a human label: `VERY_STRONG`, `STRONG`, `MODERATE`, `WEAK`, or `VERY_WEAK`. Labels are categories, not expected point values. The runner also scores monotonic skill, experience, and responsibility ladders, an obvious frontend-versus-backend mismatch, a requirements-only job description against the same requirements plus a long block of company marketing, two section orders, two paraphrases of the same work, five repeats of the fixed smoke case, and short, normal, and expanded documents.

`evaluation/results.json` stores case ids, the five internal dimension scores, the final score, inference time, and token counts. It does not store resume or job-description text. `evaluation/smoke_case.json` is the fixed regression case. Unit tests check that it returns an integer from 0 to 100 and five in-range dimension scores. They do not lock a single point value.

What is measured: category ranges, overall spread, average score on each Laya dimension, repeatability, and gaps on the controlled pairs. Weights are unchanged. Scores are not shifted, stretched, or calibrated to look better.

On the current checkpoint, five repeats of the smoke case each scored 80, so that input was repeatable. An earlier three-run check of one normal resume and job description also returned 72 each time. Laya exposes no seed parameter. The 15-case dataset did not spread across the 0–100 scale: observed scores sat between 60 and 73, and stronger category averages were only a few points above weaker ones. That is recorded in `evaluation/results.json`. Weights were left unchanged. No offset or calibration was applied.

Limits of this check: the dataset is small and synthetic, so overlap does not by itself prove a labeling error. The evaluation runner records five fresh runs of the smoke case and reports the observed range. The typed-decisions checkpoint still has a finite context, about 760 tokens of state after the question head. Long text is compacted extractively, and discarded text is not scored. A large gap between a long document and its shortened equivalent is reported for investigation rather than corrected in this step.

## Current limitations

- Laya's typed-decisions checkpoint has a finite context. The installed checkpoint uses 1024 tokens, with 256 reserved for the question head, so the combined state can use about 760 tokens. `LAYA_INPUT_TOKEN_BUDGET` defaults to that limit minus a safety margin.
- Long resumes and job descriptions are compacted deterministically before scoring. The compactor keeps higher-priority sections and cuts only on token boundaries. It does not summarize, rewrite, or invent text.
- Text that does not fit is discarded. The Match Score does not claim to reflect discarded text. A short omission marker may appear inside a truncated section that is sent to Laya.
- `Router.predict` does not expose a seed or a deterministic flag. Three identical runs of the normal resume and job description each returned 72, so scoring was deterministic for that input on this checkpoint.
- The UI shows only the Match Score. Question-level scores and token counts stay in server logs and developer scripts.
- There is no database, login, file upload, or resume rewriting.

## Future TODOs

1. Add PDF and DOCX resume upload after text scoring.
2. Replace extractive compaction with validated document chunking or a larger-context model when one is available.
