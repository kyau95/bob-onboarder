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

## Phase 4 — Bob Skill (Repository Intelligence) ⬜

**Goal:** Wire the Bob Skill to the backend API and define prompts for each capability.

### Planned Work
- Finalize `SKILL.md` instructions once backend endpoints are stable
- Understand, Explore, Analyze, and Verify prompt sections
- Backend query endpoints: `/paths`, `/impact`, `/summary`

---

## Phase 5 — Understand Capability ⬜

**Goal:** Bob can answer "explain this codebase to me."

### Planned Work
- `GET /repo/{repo_id}/summary` — language breakdown, components, APIs, test framework, build commands
- Entry point detection
- Bob-generated onboarding report

---

## Phase 6 — Explore Capability (Flow Tracing) ⬜

**Goal:** Bob can trace a request or data flow end-to-end through the graph.

### Planned Work
- `GET /repo/{repo_id}/paths?from=X&to=Y` — all simple paths with edge evidence
- Step-by-step flow narrative generation
- Natural-language Q&A over the graph

---

## Phase 7 — Analyze Capability (Impact Analysis) ⬜

**Goal:** Given a proposed change, identify everything affected.

### Planned Work
- `GET /repo/{repo_id}/impact?node=X` — BFS reachability, grouped by type
- Test file association by naming convention + imports
- Blast radius report with confidence scores
- Diff-based impact (accept a `git diff`)

---

## Phase 8 — Modify Capability (Agentic Code Change) ⬜

**Goal:** Bob implements a targeted change using its built-in agent tools.

### Planned Work
- Change scoping via Phase 7 impact analysis
- Pre-change snapshot: `POST /repo/{repo_id}/snapshot`
- Bob uses native file tools (read_file, apply_diff, write_file)
- Change log recording

---

## Phase 9 — Verify Capability (Validation + Re-analysis) ⬜

**Goal:** Run tests and regenerate the architecture model after a change.

### Planned Work
- `POST /repo/{repo_id}/test` — detect and invoke repo's test command, stream output
- Automatic re-analysis trigger after tests pass
- `GET /repo/{repo_id}/graph/diff?before=<snapshot_id>` — graph diff between snapshots
- Verification report

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
