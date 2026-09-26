# Bob the Onboarder

## Overview

Bob the Onboarder is an IBM Bob 2.0-powered developer workflow that helps engineers quickly understand and safely modify unfamiliar codebases.

The project uses a Bob Skill to analyze a repository's source code, dependencies, configuration, and Git history to build a living, evidence-backed architecture model. The model represents components, services, APIs, databases, external dependencies, and data flows within the system.

Developers can interact with the repository through Bob to:

* **Understand:** Generate an architecture overview, identify entry points, important components, build/test commands, and onboarding information.
* **Explore:** Ask questions about the codebase and trace how data or requests flow through the system.
* **Analyze:** Determine the potential impact and blast radius of a proposed change, including affected components, files, dependencies, and tests.
* **Modify:** Ask Bob to implement a targeted change using agentic workflows and subagents.
* **Verify:** Run tests and re-analyze the repository to automatically synchronize the architecture model with the updated codebase.

The goal is to reduce the time and effort developers spend manually reconstructing unfamiliar systems, tracing dependencies, and determining the consequences of changes.

## Core Concept

The architecture visualization is not the product by itself. It is the visual representation of a persistent repository intelligence model that Bob can query, reason about, and update.

The intended workflow is:

```text
Repository
    ↓
Repository Analysis
    ↓
Architecture / Dependency Model
    ↓
┌──────────┬──────────┬──────────┐
│ Understand│ Explore  │ Analyze │
└──────────┴──────────┴──────────┘
                ↓
             Modify
                ↓
             Verify
                ↓
      Updated Architecture
```

Every important architectural relationship should ideally be backed by evidence from the repository, such as source files, line numbers, configuration, or Git history.

## Technical Stack

### AI / Agent Layer

* **IBM Bob 2.0**
* **Bob Skills** for defining reusable repository-intelligence workflows
* **Agent Mode** for multi-step reasoning and implementation
* **Subagents / parallel tasks** for independent repository analysis
* Bob-supported LLM capabilities for repository reasoning and explanations

### Backend

* **Python**
* **FastAPI** — REST API and orchestration layer
* **Pydantic** — structured data models
* **Tree-sitter** — source-code parsing and AST analysis
* Python's built-in `ast` module for deeper Python-specific analysis
* **NetworkX** — dependency graph and architecture analysis
* **GitPython** or native Git commands — Git history, commits, diffs, and blame

### Architecture Model

Represent the repository as a graph consisting of:

* Components
* Services
* Modules
* Classes/functions
* APIs
* Databases
* Queues/caches
* External services
* Dependencies
* Data flows
* Git relationships

Relationships should contain evidence and confidence information where possible.

Example:

```json
{
  "source": "CheckoutService",
  "target": "PaymentService",
  "relationship": "HTTP_CALL",
  "evidence": [
    {
      "file": "checkout/service.py",
      "line": 143
    }
  ],
  "confidence": 0.97
}
```

### Frontend

* **React**
* **TypeScript**
* **React Flow** — interactive architecture/dependency visualization
* **Tailwind CSS** — lightweight UI styling

The UI should remain intentionally simple and focus on:

1. Interactive architecture graph
2. Repository Q&A/chat
3. Flow tracing
4. Impact analysis
5. Evidence/source references
6. Change/verification results

### Persistence

Start with **no database** where possible.

Use in-memory models and JSON artifacts for the hackathon MVP. If persistence becomes necessary, use:

* **SQLite** initially

Avoid adding PostgreSQL, Redis, or other infrastructure unless there is a clear requirement.

### Testing

* **pytest** — backend/unit tests
* Repository-specific test runners discovered automatically by the analysis system
* Automated validation after Bob makes code changes

### Packaging / Development

* **Git**
* **Docker / Docker Compose** for reproducible development and demonstration
* **npm / Vite** for the React frontend

## Repository Analysis Pipeline

The system should separate deterministic repository analysis from AI reasoning.

```text
                     Repository
                          │
              ┌───────────┼───────────┐
              ↓           ↓           ↓
        Source Analysis  Git       Config
          Tree-sitter   History    Analysis
              │           │           │
              └───────────┼───────────┘
                          ↓
                 Repository Model
                          ↓
                   Architecture Graph
                          ↓
                       IBM Bob
                          ↓
              Reasoning / Q&A / Analysis
```

Deterministic analysis should establish facts about the repository, while Bob should use those facts to reason about architecture, explain relationships, answer questions, analyze impact, and orchestrate modifications.

## Primary Demonstration

The final demonstration should use an unfamiliar public repository.

The workflow should be:

1. Give Bob the repository.
2. Run the Repository Intelligence Skill.
3. Bob analyzes the repository and generates an architecture model.
4. Display the resulting architecture graph.
5. Ask Bob to trace a meaningful end-to-end data/request flow.
6. Ask what would happen if a specific component or dependency were changed or removed.
7. Bob performs impact analysis and identifies affected files, components, and tests.
8. Ask Bob to make a small, controlled modification.
9. Bob implements the change, runs validation/tests, and reports the result.
10. Re-analyze the repository.
11. Show that the architecture model automatically reflects the change.

The key demonstration is that the architecture is **not a static diagram**. Bob can understand the repository, answer questions about it, analyze proposed changes, modify the code, validate the changes, and keep the architecture model synchronized with the evolving codebase.

## Initial MVP Scope

Prioritize these capabilities:

1. Repository → architecture model
2. Interactive architecture visualization
3. Natural-language repository Q&A
4. Data/request flow tracing
5. Change-impact analysis
6. Evidence-backed explanations
7. One end-to-end code modification
8. Automated validation and architecture regeneration

Avoid unnecessary infrastructure and UI complexity. The primary goal is to demonstrate how IBM Bob improves the developer workflow of **understanding, exploring, analyzing, and modifying an unfamiliar codebase**.
