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

Trigger the full analysis pipeline:

```bash
curl -s -X POST http://localhost:8000/repo/{repo_id}/analyze
```

Wait for the response, then confirm the architecture model has been generated. Report:
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

Use the returned summary JSON plus the graph to produce a structured onboarding document:
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

Format the result as a numbered step-by-step narrative. For each hop, include:
- The component/function name
- The relationship type (IMPORTS, HTTP_CALL, DB_QUERY, etc.)
- The evidence file and line number

For freeform questions ("where is auth enforced?", "what reads from the users table?"), use the
graph nodes and edges to locate the relevant components and explain their roles.

---

## Step 5 — Analyze (Impact Analysis)

When the user asks "what happens if I change/remove X?":

```bash
curl -s "http://localhost:8000/repo/{repo_id}/impact?node=<NodeName>"
```

Report the blast radius:
1. **Directly affected** — nodes with a direct edge to/from the target
2. **Transitively affected** — all reachable nodes via BFS
3. **Tests to run** — test files associated with affected source files
4. **Confidence** — per affected node, from the edge confidence scores

Warn the user about high-confidence, high-impact paths.

---

## Step 6 — Modify (Agentic Code Change)

Before making any change:
1. Run Step 5 (impact analysis) to understand the blast radius.
2. Confirm the scope with the user.
3. Record a pre-change snapshot:
   ```bash
   curl -s -X POST http://localhost:8000/repo/{repo_id}/snapshot
   ```
4. Use Bob's native file read/write/edit tools (read_file, apply_diff, write_file) to implement
   the change. Keep changes minimal and targeted.
5. Log every file changed, why it was changed, and which evidence from the graph informed the decision.

---

## Step 7 — Verify (Validation + Re-analysis)

After implementing a change:

1. Run the repository's test suite:
   ```bash
   curl -s -X POST http://localhost:8000/repo/{repo_id}/test
   ```
2. If tests fail, diagnose using the test output and fix before proceeding.
3. Re-run the analysis pipeline (Step 2) to regenerate the architecture model.
4. Fetch the graph diff to see what changed:
   ```bash
   curl -s "http://localhost:8000/repo/{repo_id}/graph/diff?before=<snapshot_id>"
   ```
5. Summarize:
   - Tests: pass/fail count and any failures
   - Architecture changes: added nodes, removed nodes, modified edges
   - Whether the changes match the original intent

---

## General Reasoning Guidelines

- Always ground claims in evidence from the repository model (file + line).
- Prefer the graph model over freeform file scanning for architectural questions.
- When the graph lacks evidence for a claim, say so and fall back to direct file inspection.
- Keep modifications minimal — only change what is necessary.
- Never add infrastructure (databases, queues, services) unless the user explicitly requests it.
