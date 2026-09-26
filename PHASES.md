# Bob the Onboarder — Implementation Progress

Track of completed phases, what was built, and the relevant files.

---

## Phase 0 — Project Scaffolding ✅

**Commit:** Phase 0 (see git log)
**Goal:** Establish the monorepo structure, install all dependencies, and wire up a minimal working backend + frontend.

### What Was Built

| Area | Details |
|------|---------|
| Repo layout | `backend/`, `frontend/`, `.bob/skills/`, `docker-compose.yml` |
| Backend | FastAPI app with `GET /health`, Pydantic settings, CORS middleware |
| Frontend | Vite + React + TypeScript, `@xyflow/react`, Tailwind CSS v4, `/api` proxy to backend |
| Docker | `docker-compose.yml` with `backend` and `frontend` services, shared `repos_data` volume |
| Bob Skill | `.bob/skills/repository-intelligence/SKILL.md` — full workflow instructions for Bob |
| Gitignore | Added project-specific patterns for `.venv`, build artifacts, runtime repo data |

### Key Files
- [`backend/app/main.py`](backend/app/main.py) — FastAPI app entry point
- [`backend/app/api/health.py`](backend/app/api/health.py) — `GET /health`
- [`backend/app/core/config.py`](backend/app/core/config.py) — Pydantic settings
- [`backend/pyproject.toml`](backend/pyproject.toml) — all backend dependencies
- [`frontend/src/App.tsx`](frontend/src/App.tsx) — minimal React scaffold
- [`frontend/vite.config.ts`](frontend/vite.config.ts) — Tailwind plugin + `/api` proxy
- [`docker-compose.yml`](docker-compose.yml)
- [`.bob/skills/repository-intelligence/SKILL.md`](.bob/skills/repository-intelligence/SKILL.md)

### Dependencies Installed

| Layer | Packages |
|-------|---------|
| Backend | `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `networkx`, `gitpython`, `tree-sitter`, `tree-sitter-python`, `tree-sitter-javascript` |
| Backend dev | `pytest`, `pytest-asyncio`, `httpx`, `ruff` |
| Frontend | `react`, `typescript`, `@xyflow/react`, `tailwindcss` (v4), `vite` |

---

## Phase 1 — Repository Ingestion ✅

**Commit:** `328972c` — `feat: Phase 1 — repository ingestion API with background cloning and startup seed`
**Goal:** Accept a repository URL, clone it in the background, track lifecycle state, and pre-seed three known repos at startup.

### What Was Built

| Area | Details |
|------|---------|
| Models | `RepoMeta`, `IngestRequest`, `IngestResponse`, `RepoSummary`, `RepoStatus` enum, `AnalysisPurpose` enum |
| Registry | Thread-safe in-memory `RepoRegistry` singleton |
| Service | `register_repo()`, `clone_repo()` (shallow background clone), `get_repo()`, `list_repos()`, `delete_repo()`, `seed_known_repos()` |
| API | `POST /repo/ingest`, `GET /repo`, `GET /repo/{repo_id}`, `DELETE /repo/{repo_id}` |
| Startup seed | Three known repos pre-registered as `PENDING` at app startup |
| Tests | 14 tests — all endpoints + service-level clone/error unit tests (14/14 passing) |
| Dev script | `start.sh` — launches backend (uvicorn `--reload`) and frontend (Vite) together with graceful Ctrl+C shutdown |

### API Endpoints

| Method | Path | Behaviour |
|--------|------|-----------|
| `POST` | `/repo/ingest` | Register + background shallow clone, returns `202` immediately |
| `GET` | `/repo` | List all repos (summary view) |
| `GET` | `/repo/{repo_id}` | Full metadata for a single repo |
| `DELETE` | `/repo/{repo_id}` | Remove registry entry + wipe local clone |

### Seeded Repositories

| Name | URL | Purpose |
|------|-----|---------|
| FastAPI Full-Stack Template | `github.com/fastapi/full-stack-fastapi-template` | development |
| Google Online Boutique | `github.com/GoogleCloudPlatform/microservices-demo` | integration |
| OpenTelemetry Astronomy Shop | `github.com/open-telemetry/opentelemetry-demo` | stress_test |

### Key Files
- [`backend/app/models/repo.py`](backend/app/models/repo.py)
- [`backend/app/core/registry.py`](backend/app/core/registry.py)
- [`backend/app/services/repo_service.py`](backend/app/services/repo_service.py)
- [`backend/app/api/repo.py`](backend/app/api/repo.py)
- [`backend/tests/test_repo.py`](backend/tests/test_repo.py)
- [`start.sh`](start.sh)

---

## Phase 2 — Deterministic Analysis Pipeline ⬜

**Goal:** Parse the repository into a raw facts model (files, imports, classes, functions, APIs, config, Git history).

### Planned Work

#### 2a — Source Analysis (Tree-sitter + `ast`)
- Language detection by file extension
- Tree-sitter parsing: modules, classes, functions, imports
- Python deep-parse: `ast` module, decorator-based route detection, DB/queue call detection
- Dependency file parsing: `requirements.txt`, `package.json`, `pyproject.toml`, `go.mod`
- API surface detection: REST routes, gRPC definitions, GraphQL schemas

#### 2b — Git History Analysis
- Commit log extraction (last N commits)
- Co-change relationship detection (files that change together)
- Hotspot detection (highest-churn files)
- Per-file ownership via blame

#### 2c — Config & Infrastructure Analysis
- `docker-compose.yml`, `.env*`, Kubernetes manifests, Terraform configs
- Service topology: named services, ports, env var references
- Build and test command discovery: `Makefile`, `package.json` scripts, `pytest.ini`, `Dockerfile`

---

## Phase 3 — Architecture Graph Construction ⬜

**Goal:** Combine all raw facts into a single NetworkX graph — the canonical representation of the repository.

### Planned Work
- Node types: `Component`, `Service`, `Module`, `Class`, `Function`, `API`, `Database`, `Queue`, `ExternalService`
- Edge types: `IMPORTS`, `CALLS`, `HTTP_CALL`, `DB_QUERY`, `PUBLISHES_TO`, `SUBSCRIBES_TO`, `CO_CHANGE`, `DEPENDS_ON`
- Evidence model: every edge carries `evidence: list[{file, line, snippet}]` and `confidence: float`
- `GraphBuilder` class combining 2a/2b/2c output into `nx.DiGraph`
- JSON serialization in React Flow node-link format
- `POST /repo/{repo_id}/analyze` and `GET /repo/{repo_id}/graph` endpoints

---

## Phase 4 — Bob Skill (Repository Intelligence) ✅

**Goal:** Wire the Bob Skill to the backend API and define prompts for each capability.

### What Was Built

| Area | Details |
|------|---------|
| Query models | `backend/app/models/query.py` — `RepoSummaryResponse`, `PathsResponse` (with `PathHop`, `PathResult`), `ImpactResponse` (with `AffectedNode`) |
| Query API | `backend/app/api/query.py` — three endpoints with DFS path-finding and BFS impact analysis |
| SKILL.md | Updated with stable endpoint paths, response field docs, corrected snapshot URL, and an API quick-reference table |
| Tests | `backend/tests/test_query.py` — 22 tests covering 404/409 guards, response structure, path finding, impact BFS, test-file detection |

### API Endpoints

| Method | Path | Capability |
|--------|------|------------|
| `GET` | `/repo/{id}/summary` | Understand — language breakdown, services, API endpoints, build commands, hotspots, entry points |
| `GET` | `/repo/{id}/paths?from=X&to=Y` | Explore — DFS simple paths, bounded to 10 paths × 8 hops, case-insensitive node matching |
| `GET` | `/repo/{id}/impact?node=X` | Analyze — BFS blast-radius: direct/transitive affected nodes + test files to run |

### Key Files
- [`backend/app/models/query.py`](backend/app/models/query.py) — response models
- [`backend/app/api/query.py`](backend/app/api/query.py) — query router
- [`.bob/skills/repository-intelligence/SKILL.md`](.bob/skills/repository-intelligence/SKILL.md) — updated skill
- [`backend/tests/test_query.py`](backend/tests/test_query.py) — 22 tests (22/22 passing)

---

## Phase 5 — Understand Capability ⬜

**Goal:** Bob can answer "explain this codebase to me."

### Planned Work
- Wire `GET /repo/{repo_id}/summary` into the skill prompt (endpoint already exists from Phase 4)
- Bob-generated onboarding summary in chat

---

## Phase 6 — Explore Capability (Flow Tracing) ⬜

**Goal:** Bob can trace a request or data flow end-to-end through the graph.

### Planned Work
- Wire `GET /repo/{repo_id}/paths?from=X&to=Y` into the skill prompt (endpoint already exists from Phase 4)
- Single-paragraph flow narrative from the returned path hops

---

## Phase 7 — Analyze Capability (Impact Analysis) ⬜

**Goal:** Given a proposed change, identify everything affected.

### Planned Work
- Wire `GET /repo/{repo_id}/impact?node=X` into the skill prompt (endpoint already exists from Phase 4)
- Blast radius summary in chat (affected nodes + suggested test files)

---

## Phase 8 — Modify Capability (Agentic Code Change) ✅

**Goal:** Bob implements a targeted change using its built-in agent tools.

### What Was Built

| Area | Details |
|------|---------|
| SKILL.md Step 6 | Updated: drop pre-change snapshot step; Bob uses native file tools scoped by Phase 7 impact output |
| SKILL.md Step 7 | Updated: simplified to just call `POST /repo/{id}/test`; graph diff removed from scope |

### Key Files
- [`.bob/skills/repository-intelligence/SKILL.md`](.bob/skills/repository-intelligence/SKILL.md) — Steps 6 & 7 updated

---

## Phase 9 — Verify Capability (Validation) ✅

**Goal:** Confirm a change didn't break anything.

### What Was Built

| Area | Details |
|------|---------|
| Model | `backend/app/models/test_run.py` — `TestRunResponse` (`passed`, `command`, `return_code`, `output`) |
| API | `POST /repo/{repo_id}/test` — detect test command from facts / fallback heuristics, run with 5-min timeout, return pass/fail + last 4 000 chars of output |
| Router | `backend/app/api/verify.py` — registered in `main.py` |
| Tests | `backend/tests/test_verify.py` — 10 tests (10/10 passing): guards, pass, fail, truncation, timeout, fallback detection |

### API Endpoints

| Method | Path | Behaviour |
|--------|------|-----------|
| `POST` | `/repo/{repo_id}/test` | Detect + invoke test command; return `passed`, `command`, `return_code`, `output` |

### Key Files
- [`backend/app/models/test_run.py`](backend/app/models/test_run.py) — response model
- [`backend/app/api/verify.py`](backend/app/api/verify.py) — verify router
- [`backend/tests/test_verify.py`](backend/tests/test_verify.py) — 10 tests (10/10 passing)

---

## Phase 10 — Frontend UI ⬜

**Goal:** A minimal, focused UI for the graph and chat-driven workflow.

### Planned Work
- React Flow graph canvas (nodes colored by type, edges labeled by relationship)
- Repository input form + status polling
- Chat/Q&A sidebar panel
- Impact analysis node highlighting
- Evidence drawer (click edge → file + line + snippet)
- Graph diff view (added = green, removed = red)

---

## Phase 11 — Integration & Demo Hardening ⬜

**Goal:** Wire everything together for the end-to-end demonstration.

### Planned Work
- Full demo run against a real public repo (PROJECT.md steps 1–11)
- Docker Compose polish (single `docker compose up`)
- Error resilience for partial analysis failures
- Demo repo selection
- README with installation and demo walkthrough
