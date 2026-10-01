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
- LangGraph, agents, RAG, embeddings, or a vector database
- Paid model APIs
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

## AI Architecture

The public Match Score is still one integer. Laya is not asked to predict an interview probability. It evaluates concrete requirements, and application code aggregates those signals. Accuracy is not established yet. LangGraph, RAG, and agents are not implemented.

```
Stage 1: LangChain + local LLM → CandidateProfile / JobProfile
Stage 2: RequirementBuilder → atomic job requirements
Stage 3: Laya → requirement-level decisions
Stage 4: Deterministic scoring → Match Score 0–100
```

1. **LangChain.** `langchain-core` builds the extraction prompts and chains. `langchain-ollama` calls a local Ollama chat model and returns a Pydantic object through `with_structured_output`. The umbrella `langchain` package is not installed, because current releases depend on LangGraph.

2. **LLM.** Ollama converts the resume into a four-field `CandidateProfile` and the job description into a five-field `JobProfile`. The prompts copy only facts that appear in the source text. Placeholder strings such as "None" are rejected. The model does not score the candidate.

3. **Requirement builder.** `JobProfile` becomes explicit requirements: `REQUIRED_SKILL`, `PREFERRED_SKILL`, `RESPONSIBILITY`, `EXPERIENCE`, and `ROLE`.

4. **Laya, requirement level.** With `REQUIREMENT_MATCHING_ENABLED=true`, each skill, responsibility, and role is a typed question over the candidate profile only. Skills and responsibilities use `noul`, which returns the probability that the answer is yes. Role uses a three-way `choice` (`MATCH`, `PARTIAL_MATCH`, `NO_MATCH`). Experience is a deterministic comparison and is not sent to Laya. Questions that fit the checkpoint go in one `Router.predict` call; otherwise they are split in category order. The typed-decisions checkpoint budgets `head_max_len` per question, not as one shared pool of questions.

5. **Score.** Required skills are 55% of the score, responsibilities 15%, experience 15%, role 10%, and preferred skills 5%. The weights live in configuration. The broad five-question Laya score remains available as `BroadLayaScoringService` and is still the public path while `REQUIREMENT_MATCHING_ENABLED=false`. `LLM_EXTRACTION_ENABLED=true` can still feed extracted text to that broad path. The HTTP response remains `{ "score": N }`. Requirement probabilities stay internal.

Compare the two scorers on fixed examples:

```powershell
.\.venv\Scripts\python.exe -m evaluation.compare_scoring
```

Ollama has to be running on this machine before extraction will work. Install it from [ollama.com](https://ollama.com), start the app, and pull a chat model that supports structured output:

```powershell
ollama pull qwen2.5:1.5b-instruct-q5_K_M
```

Use another installed model by setting `LLM_MODEL`. Inspect an extraction without changing the score API:

```powershell
.\.venv\Scripts\python.exe -m evaluation.test_extraction
```

## Laya Decision Primitive Evaluation

Requirement-level questions currently use `noul`. Laya 0.3.21 treats `noul` as label-sensitive and documents a neutral two-option `choice` as a workaround. This benchmark compares those primitives on the same candidate state and requirement. It does not change `REQUIREMENT_MATCHING_ENABLED`, which remains `false`.

Each case is asked twice in one `Router.predict` call: once as `noul`, and once as a `choice` whose labels are only `A` and `B`. `A` means the candidate evidence supports the requirement. `B` means it does not. A second call swaps those meanings so `A` means the evidence does not support the requirement and `B` means it does. The decision being asked does not change. `noul` probabilities at or above 0.5 count as MATCH. The label swap is a bias check, not a calibration.

Run it with:

```powershell
.\.venv\Scripts\python.exe -m evaluation.run_laya_decision_benchmark
```

On this machine, with the installed typed-decisions checkpoint:

| Set | noul accuracy | choice accuracy | noul false positives | choice false positives | label-swap changes |
| --- | --- | --- | --- | --- | --- |
| 15 controlled cases | 0.933 | 0.467 | 1 | 8 | 3 of 15 |
| Relationship Manager requirements | 0.000 | 0.000 | 10 of 10 | 10 of 10 | 0 of 10 |
| Strong backend requirements | 1.000 | 1.000 | 0 | 0 | 0 of 5 |

`noul` missed only the "event-driven services" versus "Kafka experience" case, at probability 0.506. The neutral `choice` predicted MATCH for 8 of the 9 controlled NO_MATCH cases, and 3 of those 15 answers flipped when the A/B meanings were swapped. Both primitives predicted MATCH for every Relationship Manager requirement against the software-engineer profile, with `noul` probabilities about 0.63–0.66. Both predicted MATCH for Java, Spring Boot, PostgreSQL, Kafka, and REST APIs on the strong backend profile.

This run does not justify replacing `noul` in production. The neutral `choice` was less accurate and label-sensitive on the controlled set. `noul` was the better of the two there, and it still does not reject the relationship-manager mismatch. Production scoring is unchanged.

## Local LLM Model Selection

`llama3.1` is a poor fit for this 8 GB Windows machine. Ollama 0.34.4 loads it at about 5.3 GB and runs it on CPU. A plain prompt returns text, and a two-field JSON schema can return values, but the full `CandidateProfile` / `JobProfile` schema either comes back empty or stalls. One full call took about 100 seconds.

Three smaller models were run one at a time with the same prompts, schemas, and the fintech resume plus the Senior Relationship Manager job description. Structured output used `with_structured_output` in `json_schema` mode. Profiles were not edited after the model returned them. The benchmark does not call Laya.

| Model | Resume | Job | Total | Quality | Notes |
| --- | --- | --- | --- | --- | --- |
| `qwen2.5:1.5b-instruct-q5_K_M` (1.2 GB) | PASS, 39 s | FAIL, 19 s | 59 s | FAIL | Resume skills are mostly present. The job title is present, but the duty list is empty. |
| `llama3.2:1b` (1.5 GB) | FAIL, 20 s | FAIL, 7 s | 27 s | FAIL | Valid JSON with empty profiles. |
| `llama3.2:3b` (2.3 GB) | PASS, 58 s | FAIL, 32 s | 91 s | FAIL | Similar job miss to Qwen, slower and larger. |

The default `LLM_MODEL` is `qwen2.5:1.5b-instruct-q5_K_M` because it is the smallest model that returned a non-empty resume and job title on this hardware, in under a minute total. `LLM_MODEL` is still an environment variable. None of the three models copied the job's village-survey and collections duties into `responsibilities` on that larger schema. The profiles were later reduced to four candidate fields and five job fields so this model has a smaller structured-output target. That reduction does not change the Laya score.

## Technology stack

| Area | Stack |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Java 21, Spring Boot 4.1.1, Maven |
| AI service | Python 3.10+, FastAPI, Laya 0.3.21 (`typed-decisions`), LangChain core, Ollama |

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
| `LLM_PROVIDER` | AI service | `ollama` |
| `OLLAMA_BASE_URL` | AI service | `http://localhost:11434` |
| `LLM_MODEL` | AI service | `qwen2.5:1.5b-instruct-q5_K_M` |
| `LLM_EXTRACTION_ENABLED` | AI service | `false` |
| `REQUIREMENT_MATCHING_ENABLED` | AI service | `false`; `true` selects requirement-level scoring |
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
