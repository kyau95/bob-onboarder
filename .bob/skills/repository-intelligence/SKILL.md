---
name: repository-intelligence
description: Use when the user wants to analyze a repository, understand its architecture, explore data flows, run impact analysis on a proposed change, modify code, or verify changes — activates the Bob the Onboarder repository intelligence workflow.
---

# Repository Intelligence Skill

This skill guides Bob through the full Bob the Onboarder workflow: ingest a repository, build its
architecture model via the backend API, and then reason over it to answer questions, trace flows,
analyze impact, implement changes, and verify results.

## Backend Base URL

The backend API runs at `http://localhost:8000` by default. If the user specifies a different URL,
use that instead.

---

## Step 1 — Ingest the Repository

When the user provides a repository URL or local path:

1. Call `POST /repo/ingest` with `{ "url": "<repo_url>" }` using the `execute_command` tool:
   ```bash
   curl -s -X POST http://localhost:8000/repo/ingest \
     -H "Content-Type: application/json" \
     -d '{"url": "<repo_url>"}'
   ```
2. Capture the returned `repo_id`.
3. Poll `GET /repo/{repo_id}` until `status` is `"ready"`.
4. Confirm to the user that ingestion is complete.

---

## Step 2 — Analyze the Repository

Trigger the deterministic analysis pipeline (source + git + config facts):

```bash
curl -s -X POST http://localhost:8000/repo/{repo_id}/analyze
```

Poll `GET /repo/{repo_id}` until `status` is `"analyzed"`.

Then build the architecture graph from the raw facts:

```bash
curl -s -X POST http://localhost:8000/repo/{repo_id}/graph/build
```

Poll `GET /repo/{repo_id}/graph` until the response has `node_count > 0`.  Then report:
- Number of nodes (components, services, classes, APIs, etc.)
- Number of edges (relationships)
- Detected languages and frameworks
- Discovered build/test commands

---

## Step 3 — Understand (Architecture Overview)

When the user asks for an overview or "explain this codebase":

```bash
curl -s http://localhost:8000/repo/{repo_id}/summary
```

The response includes:
- `language_breakdown` — file counts per language
- `services` — named deployable services
- `api_endpoints` — all detected HTTP routes
- `dependencies` — external packages
- `build_commands` — discovered build/test/run commands
- `hotspots` — highest-churn files (git history)
- `entry_points` — detected main files

Use this JSON plus the full graph to produce a structured onboarding document covering:
- What the system does
- Top-level services and their responsibilities
- Key entry points (main files, API routes, CLI commands)
- How to build and run the system
- How to run the tests

Every claim should reference evidence (file path + line number) from the model.

---

## Step 4 — Explore (Flow Tracing)

When the user asks "how does X flow through the system?" or "trace the path from A to B":

```bash
curl -s "http://localhost:8000/repo/{repo_id}/paths?from=<NodeA>&to=<NodeB>"
```

- `from` and `to` are **case-insensitive substring** matches against node labels or IDs.
- The response contains `paths`, each with a list of `hops`.
- Each hop has a `node` (label, type, file) and an `edge` (type, evidence, confidence).

Format the result as a numbered step-by-step narrative. For each hop, include:
- The component/function name
- The relationship type (IMPORTS, HTTP_CALL, DB_QUERY, CO_CHANGE, etc.)
- The evidence file and line number

For freeform questions ("where is auth enforced?", "what reads from the users table?"), fetch the
full graph and search the node labels and edge evidence for relevant components:

```bash
curl -s http://localhost:8000/repo/{repo_id}/graph
```

---

## Step 5 — Analyze (Impact Analysis)

When the user asks "what happens if I change/remove X?":

```bash
curl -s "http://localhost:8000/repo/{repo_id}/impact?node=<NodeNameOrID>"
```

The response contains:
- `target_node` — the node being changed
- `direct` — nodes with a direct edge to/from the target (distance = 1)
- `transitive` — all reachable nodes via BFS (distance ≥ 2)
- `tests_to_run` — test files associated with affected source files
- `total_affected` — total count of affected nodes

Report the blast radius in three sections:
1. **Directly affected** — list `direct` nodes with their edge type and confidence
2. **Transitively affected** — list `transitive` nodes grouped by distance
3. **Tests to run** — list `tests_to_run`

Warn the user about high-confidence, high-impact paths (`max_confidence ≥ 0.8`).

---

## Step 6 — Modify (Agentic Code Change)

Before making any change:
1. Run Step 5 (impact analysis) to understand the blast radius.
2. Confirm the scope with the user.
3. Use Bob's native file read/write/edit tools (read_file, apply_diff, write_file) to implement
   the change. Keep changes minimal and targeted.
4. Log every file changed, why it was changed, and which evidence from the graph informed the decision.

---

## Step 7 — Verify (Validation)

After implementing a change, run the repository's test suite:

```bash
curl -s -X POST http://localhost:8000/repo/{repo_id}/test
```

The response contains:
- `passed` — `true` if the test command exited 0, `false` otherwise
- `command` — the test command that was run
- `output` — combined stdout + stderr (last 4 000 characters)
- `return_code` — raw process exit code

If `passed` is `true`, report success and summarise what was changed.
If `passed` is `false`, show the relevant lines from `output` and help the user fix the failure.

---

## API Quick Reference

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/repo/ingest` | Ingest a repository URL |
| `GET`  | `/repo/{id}` | Poll ingestion / analysis status |
| `GET`  | `/repo` | List all repositories |
| `DELETE` | `/repo/{id}` | Remove a repository |
| `POST` | `/repo/{id}/analyze` | Trigger raw-facts analysis |
| `GET`  | `/repo/{id}/raw-facts` | Fetch raw analysis facts |
| `POST` | `/repo/{id}/graph/build` | Build architecture graph from facts |
| `GET`  | `/repo/{id}/graph` | Fetch the architecture graph |
| `GET`  | `/repo/{id}/graph/react-flow` | Graph in React Flow format |
| `POST` | `/repo/{id}/graph/snapshot` | Snapshot the current graph |
| `GET`  | `/repo/{id}/graph/diff?before=<snap_id>` | Diff current graph vs snapshot |
| `GET`  | `/repo/{id}/summary` | High-level architecture overview (Understand) |
| `GET`  | `/repo/{id}/paths?from=X&to=Y` | Flow tracing between nodes (Explore) |
| `GET`  | `/repo/{id}/impact?node=X` | Blast-radius analysis (Analyze) |
| `POST` | `/repo/{id}/test` | Run the repo's test suite (Verify) |

---

## General Reasoning Guidelines

- Always ground claims in evidence from the repository model (file + line).
- Prefer the graph model over freeform file scanning for architectural questions.
- When the graph lacks evidence for a claim, say so and fall back to direct file inspection.
- Keep modifications minimal — only change what is necessary.
- Never add infrastructure (databases, queues, services) unless the user explicitly requests it.
