# CivicLoop

**An open-weight AI agent for persistent civic problem management**

CivicLoop is a proposed civic-tech project focused on helping residents maintain continuity across civic complaints and follow those complaints beyond their initial registration. The initial prototype is scoped to **Bengaluru, Karnataka**, with a focus on **garbage accumulation and blocked drainage**.

> **Project status:** This README describes the proposed design and MVP from the technical blueprint. It does not claim that the application, integrations, or features are already implemented or deployed.

## The problem

Reporting a civic issue and getting the underlying problem resolved are different tasks. A resident may have multiple complaint IDs, receipts, screenshots, updates, and follow-up conversations. These records can be spread across channels, and the resident may need to work out which department or next step is relevant.

A complaint's administrative status is also not the same as proof that the physical issue has been resolved. CivicLoop aims to help residents maintain a clear case history, understand their next permitted action, and record whether the outcome has actually been verified.

## Proposed solution

CivicLoop is designed as an assisting layer around existing civic channels—not as a replacement for government portals. It combines a persistent case record, verified source guidance, a bounded AI agent, and scheduled follow-up tasks.

The AI model is intended to contribute meaningfully by interpreting citizen requests, extracting candidate fields from supplied records, suggesting related cases, choosing from permitted tools, and explaining next steps with source references. Deterministic backend code remains responsible for permissions, validation, state transitions, scheduling, and external actions.

## MVP scope

- **Geography:** Bengaluru, represented as configurable reference data.
- **Issue categories:** garbage accumulation and blocked drainage.
- **Intake:** manually enter complaint details or import a receipt, screenshot, complaint reference, or citizen observation.
- **Unified case page:** linked complaint records, evidence references, event timeline, next action, and outcome-verification state.
- **Verified guidance:** retrieve from a curated registry of official sources and show the source and last-checked information.
- **Persistent follow-up:** save reminders and workflow tasks so they can resume after a restart; use bounded retries for transient failures.
- **Closure verification:** record the citizen's observation separately from the administrative status reported by a source.
- **Human approval:** require explicit approval before consequential external actions. The MVP drafts or recommends an action; it does not submit a government application automatically.

## Core features

### 1. Cross-Portal Case Continuity

Keep complaint records from different channels attached to a single CivicLoop case. The system can suggest links based on shared attributes such as issue category, approximate location, date, and source reference. A user confirms or rejects suggested links; the AI must not silently merge records or change original complaint identifiers.

### 2. Evidence-Based Closure Verification

Track the status reported by the source separately from CivicLoop's record of the observed outcome. Example outcome states:

- `AWAITING_VERIFICATION`
- `CITIZEN_CONFIRMED_RESOLVED`
- `RESOLUTION_DISPUTED`
- `INSUFFICIENT_EVIDENCE`

A closure message or photograph alone is not treated as conclusive proof of a lasting resolution. The case should retain provenance, timestamps, and uncertainty.

### 3. Multi-Department Dependency Agent

Use a curated responsibility registry to help identify relevant departments, guidance, and next steps. Recommendations should include a source URL and last-verification date. If the responsible body, deadline, or next step cannot be verified, the system should state that uncertainty rather than invent an answer.

### 4. Persistent Agent Follow-Through

Store workflow tasks durably, including their due time, status, retry count, and associated case. A database-backed task record and worker queue allow follow-up to resume after interruption. Retries must be bounded and should not repeat external actions unsafely.

Live status checks are only possible when an authorised, reliable connector exists. Otherwise, CivicLoop should ask the resident to upload an update or record the status manually; it must not pretend that a live check occurred.

### 5. Community Incident Intelligence (later MVP expansion)

Aggregate consented reports by approximate area, issue category, and time period to highlight possible recurring problems. Deduplicate likely repeats, show sample sizes and uncertainty, and avoid publishing personal details or individual case histories by default. This is a **P2 / expansion feature**, not a prerequisite for the first end-to-end demo.

### 6. Auditable Case Timeline

Maintain a traceable event history with event type, timestamp, actor, source, and relevant evidence or workflow-task references. Keep citizen-reported observations, externally sourced facts, AI-generated proposals, and backend-verified state changes distinguishable. The timeline should be append-oriented rather than silently rewriting past events.

## Typical workflow

1. A resident creates a case or imports a complaint receipt or screenshot.
2. CivicLoop extracts candidate fields and asks the resident to confirm uncertain details.
3. The system retrieves relevant official guidance and suggests possible related records.
4. The resident confirms or rejects suggested links; the case timeline is updated.
5. The AI proposes a next action with source references. Backend policy checks validate the proposal.
6. The resident approves any consequential action. Without an authorised integration, CivicLoop provides guidance or a draft rather than submitting it.
7. A follow-up task is saved and scheduled where appropriate.
8. When a source reports closure, CivicLoop asks the resident to verify the real-world outcome and records it as confirmed, disputed, or insufficiently evidenced.

## Recommended technology stack

| Layer | Proposed technology | Responsibility |
|---|---|---|
| Frontend | React, TypeScript, Vite | Case views, intake, timelines, evidence and approval UI |
| UI and data fetching | Tailwind CSS, accessible component primitives, TanStack Query, React Router | Styling, navigation, and server-state handling |
| API backend | Python, FastAPI, Pydantic | Validated API endpoints and policy enforcement |
| Relational database | PostgreSQL, SQLAlchemy 2.x, Alembic | Source of truth for cases, events, links, sources, consent, and workflow metadata |
| Background work | Celery with Redis | Scheduled follow-ups, task execution, retries, and worker queues |
| AI inference | Gemma 4 through a model-provider adapter; Ollama considered for local development | Request understanding, extraction, bounded tool selection, and explanations |
| Document extraction | Tesseract OCR, PyMuPDF, deterministic field parsers | Extract candidate text and fields from supported screenshots and PDFs |
| Evidence storage | Private local volume for development; S3-compatible storage for production if needed | Store evidence separately from relational metadata |
| Tests and quality | pytest, HTTPX/FastAPI test client, frontend tests, Ruff, and type checking | Validate API, agent tools, workflow recovery, and frontend behavior |
| Local deployment | Docker Compose | Run the API, database, Redis, and worker consistently in development |

**Model note:** The exact Gemma 4 variant, serving configuration, hardware requirements, and model licence must be verified before implementation. Keep the model provider behind an adapter so the workflow and policy logic do not depend on a particular inference server.

## High-level architecture

```text
Resident / Community User
          |
          v
React + TypeScript Frontend
          |
          v
FastAPI API  ---- validation, authentication, permissions, policy checks
          |
          v
Modular case service + bounded AI-agent orchestrator
       |                 |                    |
       v                 v                    v
  PostgreSQL       Gemma 4 adapter      Verified source connectors
  durable state    model inference      and knowledge retrieval
       |
       v
  Redis + Celery worker ---> scheduled follow-ups and bounded retries
       |
       v
  Private evidence storage (files kept separate from metadata)
```

The model does not get direct, unrestricted database access. It proposes typed tool calls; the server validates arguments, permissions, and policy before executing any action. PostgreSQL is the durable source of truth. Redis is used for queueing and worker coordination, not as the only record of a case or scheduled task.

## Data model (planned)

The initial relational model is expected to include:

- `users` — account or delegated identity references and preferences.
- `cases` — the persistent CivicLoop case and current lifecycle state.
- `complaint_records` — source complaint references and imported status details.
- `case_events` — append-oriented timeline events.
- `evidence` — private file-storage references, hashes, timestamps, and metadata.
- `workflow_tasks` — durable follow-up tasks, status, due time, retries, and errors.
- `case_links` — confirmed relationships between records or cases.
- `sources` and `knowledge_items` — official source registry and reviewed guidance.
- `consent_records` — user consent for sharing or aggregation where applicable.

Collect only the data needed for the workflow. Define evidence retention and deletion behavior before accepting real citizen documents. Do not commit real complaint receipts, personal details, access tokens, API keys, or private evidence to the repository.

## Source and data strategy

CivicLoop is intended to use a curated registry of official civic portals, department responsibilities, service guidance, and published standards. Each source should record its jurisdiction, topic, source URL, retrieval method, and last-checked timestamp.

For the first prototype, user-supplied receipts, screenshots, complaint references, dates, and observations can support the workflow without pretending that a government integration exists. Synthetic test records should be clearly labelled as synthetic. Public discussions may help discover user pain points, but they are not authoritative sources for policy, deadlines, or responsibility.

## Safety, privacy, and reliability

- **Human approval:** external or consequential actions require explicit user approval and an authorised integration.
- **No portal bypass:** do not bypass logins, CAPTCHAs, rate limits, access controls, or private APIs.
- **Source provenance:** show where guidance came from and when it was last checked; disclose stale or unavailable sources.
- **Untrusted uploads:** treat uploaded files and extracted text as data, not as instructions to the AI agent.
- **Minimum data:** avoid collecting unnecessary personal data; keep evidence private; provide user-controlled deletion where supported.
- **Responsible aggregation:** do not publish individual case details by default. Use consent, deduplication, privacy safeguards, and clear sample sizes for any community-level view.
- **Honest status:** distinguish source-reported status, user-reported observation, AI suggestion, and backend-verified state.
- **Resilient tasks:** persist scheduled work, use bounded retries with backoff, and expose failed tasks rather than silently dropping them.
- **No unsupported prediction:** do not predict severity, deadlines, or resolution probability until suitable validated data and evaluation exist.

## Testing and evaluation

The prototype should be evaluated on complete workflows, not only on whether the model produces fluent text. Planned measures include:

- **Case-link precision:** how many suggested links users or reviewers confirm as valid.
- **Routing correctness:** whether recommended responsibility and next steps match reviewed official guidance.
- **Tool-call success:** whether proposed tools are valid, authorised, and executed safely.
- **Source traceability:** whether factual recommendations cite an appropriate source.
- **Recovery after restart:** whether scheduled work resumes without duplicate effects or lost state.
- **Outcome-state integrity:** whether administrative closure remains separate from citizen-verified outcome.
- **Latency and failure handling:** API and model latency, retries, worker failures, and fallback behavior.
- **Privacy and permission checks:** unauthorised access, oversized uploads, invalid inputs, and deletion behavior.

Report measured results from actual tests. Do not present target values, simulated examples, or planned tests as achieved results.

## Demo plan

A suggested 3–4 minute demonstration:

1. Import a sample garbage-accumulation complaint receipt.
2. Show extracted fields and ask the user to confirm uncertain values.
3. Suggest a related record and let the user confirm or reject the link.
4. Retrieve official guidance with a visible source reference.
5. Show the administrative status as closed while the citizen observation says the problem remains.
6. Propose a safe next step, require approval where necessary, and save a follow-up task.
7. Restart or interrupt the worker and demonstrate that the task resumes without duplicate effects.
8. Record the outcome as disputed or citizen-confirmed only after the appropriate verification step.

If a live government connector is not available, use clearly labelled synthetic or manually entered records. Do not represent simulated events as live portal status.

## Development approach

The recommended first version is a **modular monolith**: one API application and a separate worker process using the same codebase, with PostgreSQL as the source of truth. Keep the AI agent bounded and tool-based. Avoid adding Kubernetes, multiple microservices, a multi-agent framework, or a vector database until a demonstrated requirement justifies the extra complexity.

The final repository should include the actual project configuration, environment variable template, migrations, sample data, tests, architecture diagram, and reproducible local-run instructions. Update this section with verified setup commands once those files are present.

## Current limitations

- The initial prototype is limited to Bengaluru and two issue categories.
- Government portal integrations and automatic complaint submission are out of scope unless an authorised integration is available and approved.
- Live status monitoring is unavailable where no reliable authorised source connector exists.
- OCR and AI extraction may be uncertain; users must be able to review and correct extracted data.
- Community incident analytics require sufficient consented data and careful privacy safeguards.
- A recorded or citizen-confirmed outcome is not a guarantee that an issue will remain resolved permanently.

## Roadmap

1. Implement the case model, timeline, evidence references, and manual-first intake.
2. Add source registry and reviewed official guidance retrieval.
3. Integrate Gemma 4 for extraction, related-case suggestions, bounded tool selection, and explanations.
4. Add durable follow-up tasks, retry handling, and restart-recovery tests.
5. Complete the closure-verification workflow and evaluation suite.
6. Consider community-level incident intelligence, additional categories, local-language workflows, and authorised integrations only after the core workflow is reliable.

## Contributing

Contributions should preserve the project’s principles: traceable sources, clear separation between facts and suggestions, explicit permission checks, durable workflows, and privacy by default. Add tests for new tools and workflow transitions. Do not submit real citizen data, credentials, or private evidence.

Before public release, select and include an appropriate open-source licence for this repository, and verify the model licence and the terms of use for any external data or sources.

## Acknowledgement

CivicLoop is intended to complement existing civic reporting channels by helping residents maintain continuity across complaint records and follow up toward a verifiable outcome.
