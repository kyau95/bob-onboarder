# Bob the Onboarder

> **Repository intelligence powered by IBM Bob.**  
> Ingest any public Git repository, build its architecture graph, explore data flows, run impact analysis, and verify changes — all through a visual UI and an AI-powered Bob skill.

---

## What it does

Bob the Onboarder analyses a cloned repository with a deterministic pipeline (source parsing, git history, config files), builds a live architecture graph, and exposes it through three complementary interfaces:

| Interface | How to use it |
|-----------|--------------|
| **Visual UI** | Two-pane React app — graph canvas with custom nodes, edge evidence drawer, and impact highlighting |
| **REST API** | FastAPI backend with interactive docs at `http://localhost:8000/docs` |
| **Bob Skill** | Activate the `repository-intelligence` skill in IBM Bob to answer questions, trace flows, and make changes through conversation |

---

## Prerequisites

| Tool | Minimum version | Check |
|------|----------------|-------|
| Python | 3.11 | `python3 --version` |
| Node.js | 18 | `node --version` |
| npm | 9 | `npm --version` |
| Git | any | `git --version` |

Docker is optional (see [Docker Compose](#option-b-docker-compose)).

---

## Getting started

### Option A — Local dev (recommended)

**1. Clone the repo**

```bash
git clone https://github.com/kyau95/bob-onboarder.git
cd bob-onboarder
```

**2. Set up the Python virtual environment**

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e "backend[dev]"
```

**3. Install frontend dependencies**

```bash
npm install --prefix frontend
```

**4. Start both services**

```bash
./start.sh
```

This launches:
- Backend → `http://localhost:8000` (hot-reload on)
- Frontend → `http://localhost:5173`
- API docs → `http://localhost:8000/docs`

Stop everything with **Ctrl+C**.

---

### Option B — Docker Compose

```bash
docker compose up --build
```

- Frontend → `http://localhost:5173`
- Backend → `http://localhost:8000`

The `repos_data` volume persists cloned repositories across restarts.

---

## Using the Visual UI

Open **`http://localhost:5173`** in your browser.

### Step 1 — Ingest a repository

Paste any public GitHub URL into the input field at the top of the sidebar and click **Ingest**.

```
https://github.com/fastapi/full-stack-fastapi-template
```

The status badge advances automatically through the full pipeline:

```
pending → cloning → ready → analyzing → analyzed
```

When it reaches **analyzed**, the graph is built and displayed on the canvas automatically.

> Three repositories are pre-seeded at startup (FastAPI template, Google Online Boutique, OpenTelemetry demo). Select any of them from the sidebar and click **Analyze →** to build their graphs without re-cloning.

---

### Step 2 — Explore the architecture graph

The main canvas shows the full architecture graph for the selected repository.

**Nodes** are colour-coded by type:

| Colour | Node type | What it represents |
|--------|----------|--------------------|
| Blue | `service` | A distinct deployable service |
| Indigo | `component` | A logical module or package |
| Slate | `module` | A source file |
| Amber | `class` | A class definition |
| Green | `function` | A function or method |
| Pink | `api_endpoint` | An HTTP route |
| Yellow | `database` | A database |
| Red | `queue` | A message queue |
| Light green | `cache` | A cache layer |
| Purple | `external` | A third-party service |
| Light slate | `dependency` | An external package |

**Edges** are labelled with the relationship type (`IMPORTS`, `CALLS`, `HTTP_CALL`, `DB_QUERY`, `CO_CHANGE`, `EXPOSES`, …) and animated for call/HTTP relationships.

**Canvas controls:**
- Scroll to zoom, drag to pan
- Use the **minimap** (bottom-right) for orientation
- Click **fit view** (controls, bottom-left) to reset zoom
- Drag individual nodes to rearrange

---

### Step 3 — Inspect edge evidence

Click any **edge** on the canvas to open the **Evidence Drawer** on the right.

It shows every piece of evidence backing that relationship:

```
app/main.py:12
  from .service import ItemService
```

Each entry includes the **file path**, **line number**, and the **source snippet** that was detected.

---

### Step 4 — Run impact analysis

In the **Impact Analysis** panel at the bottom of the sidebar:

1. Type a node label or partial name (e.g. `utils`, `ItemService`, `GET /items`)
2. Click **Run**

The canvas immediately:
- **Highlights** the target node and all affected nodes with an orange glow
- **Dims** everything else
- Lists affected nodes grouped by distance and their suggested test files

Click **Clear** to reset the highlighting.

---

## Using the API directly

The full REST API is documented interactively at **`http://localhost:8000/docs`**.

### Core workflow

```bash
# 1. Ingest a repository (returns repo_id immediately)
curl -s -X POST http://localhost:8000/repo/ingest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/fastapi/full-stack-fastapi-template"}'

# 2. Poll until status is "ready"
curl -s http://localhost:8000/repo/<repo_id> | jq .status

# 3. Run the analysis pipeline
curl -s -X POST http://localhost:8000/repo/<repo_id>/analyze

# 4. Poll until status is "analyzed"
curl -s http://localhost:8000/repo/<repo_id> | jq .status

# 5. Build the architecture graph
curl -s -X POST http://localhost:8000/repo/<repo_id>/graph/build

# 6. Fetch the graph (node_count > 0 means it's ready)
curl -s http://localhost:8000/repo/<repo_id>/graph | jq '{nodes: .node_count, edges: .edge_count}'
```

### Intelligence queries

```bash
# Understand — high-level architecture overview
curl -s http://localhost:8000/repo/<repo_id>/summary | jq .

# Explore — trace a path between two nodes
curl -s "http://localhost:8000/repo/<repo_id>/paths?from=main&to=database" | jq .

# Analyze — blast radius of changing a node
curl -s "http://localhost:8000/repo/<repo_id>/impact?node=ItemService" | jq .

# Verify — run the repo's test suite
curl -s -X POST http://localhost:8000/repo/<repo_id>/test | jq '{passed, command, return_code}'
```

### Full API reference

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/repo/ingest` | Ingest a repository URL |
| `GET` | `/repo` | List all repositories |
| `GET` | `/repo/{id}` | Poll status / full metadata |
| `DELETE` | `/repo/{id}` | Remove repo + local clone |
| `POST` | `/repo/{id}/analyze` | Run analysis pipeline |
| `GET` | `/repo/{id}/raw-facts` | Fetch raw analysis facts |
| `POST` | `/repo/{id}/graph/build` | Build architecture graph |
| `GET` | `/repo/{id}/graph` | Fetch the full graph |
| `GET` | `/repo/{id}/graph/react-flow` | Graph in React Flow format |
| `GET` | `/repo/{id}/summary` | High-level overview (Understand) |
| `GET` | `/repo/{id}/paths?from=X&to=Y` | Flow tracing (Explore) |
| `GET` | `/repo/{id}/impact?node=X` | Blast-radius analysis (Analyze) |
| `POST` | `/repo/{id}/test` | Run test suite (Verify) |

---

## Using the Bob Skill

The `repository-intelligence` skill wires Bob directly to the backend API.

### Activate the skill

In IBM Bob, the skill activates automatically when you ask anything about analysing a repository. The full workflow is documented in [`.bob/skills/repository-intelligence/SKILL.md`](.bob/skills/repository-intelligence/SKILL.md).

### Example conversations

**Understand the codebase**
```
Explain the architecture of https://github.com/fastapi/full-stack-fastapi-template
```
Bob ingests the repo, builds the graph, calls `/summary`, and produces a structured onboarding document.

**Trace a data flow**
```
How does a request to POST /items flow through the system?
```
Bob calls `/paths?from=POST /items&to=database` and narrates each hop with file references.

**Impact analysis**
```
What breaks if I change the ItemService class?
```
Bob calls `/impact?node=ItemService`, lists directly and transitively affected components, and suggests which tests to run.

**Make a change**
```
Rename the get_items function to list_items and update all callers
```
Bob runs impact analysis first, then uses its native file tools (`read_file`, `apply_diff`) to implement the change with minimal scope.

**Verify the change**
```
Run the tests
```
Bob calls `POST /repo/{id}/test` and reports pass/fail with the relevant output lines.

---

## Running the backend tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

Expected: **99 tests, 99 passing**.

---

## Project structure

```
bob-onboarder/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (repo, analysis, graph, query, verify)
│   │   ├── core/         # Config, registry, graph store
│   │   ├── models/       # Pydantic models (repo, facts, graph, query, test_run)
│   │   └── services/     # Analysis pipeline, graph builder, serializer
│   ├── tests/            # 99 pytest tests
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── components/   # GraphCanvas, ImpactPanel, RepoIngestForm, Sidebar
│       ├── api.ts        # API client
│       ├── types.ts      # Shared TypeScript types
│       └── useRepoPolling.ts
├── .bob/skills/
│   └── repository-intelligence/SKILL.md
├── docker-compose.yml
├── start.sh              # One-command local dev launcher
└── PHASES.md             # Implementation progress log
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, Pydantic v2, NetworkX, GitPython, Tree-sitter |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, `@xyflow/react` |
| AI | IBM Bob 2.0 with custom `repository-intelligence` skill |
| Infrastructure | Docker Compose, shared `repos_data` volume |
