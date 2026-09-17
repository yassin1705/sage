# SAGE

**Secretary Agent for Guidance and Engagement**

SAGE is an evidence-backed customer-service assistant for dealerships. It brings
customer enquiries from multiple communication channels into one review
workflow, prepares a response from the available operational evidence, and
keeps a human manager in control of uncertain or high-impact answers.

> AI prepares the answer. Evidence explains it. A human stays in control.

## The problem

Customers contact dealerships through WhatsApp, email, web chat, and phone
calls. They may speak different languages, and they often need a quick answer
to a simple question such as:

> When can I collect my car?

Answering safely can require someone to check messages, workshop progress,
quality-control records, bookings, and CRM data. When those systems disagree,
staff may repeat work or make a promise the dealership cannot keep.

## The SAGE workflow

1. A customer asks a question through the customer portal.
2. SAGE identifies the request and the relevant vehicle case.
3. It gathers evidence from the available synthetic records.
4. Deterministic rules detect missing or conflicting information.
5. SAGE prepares a response and explains its recommendation.
6. A manager approves, edits, or rejects the proposed response.
7. The approved response is returned to the customer through a simulated
   delivery channel.

## Current features

### Customer portal

- Conversational customer interface.
- English and French language selection.
- Suggested customer questions.
- Visible case and review status.
- Responsive desktop and mobile design.
- Voice controls displayed as a planned capability.

### Manager workspace

- Unified customer-inquiry queue.
- Search and review-status filters.
- Predefined request classifications with manual correction.
- Agent confidence, justification, and triggered business rules.
- Evidence snapshots from workshop, CRM, and quality-control records.
- Editable proposed responses.
- Simulated approval, rejection, and delivery workflow.
- Simulated WhatsApp and Gmail configuration area.

### Shared database

- SQLite schema shared by both applications.
- Customers, vehicles, service jobs, and source-specific status events.
- Conversations, messages, classifications, and decisions.
- Evidence snapshots, human reviews, channel configuration, and audit events.
- Repeatable synthetic C01 seed data.

## Architecture

```text
Customer portal ──┐
                  ├── Shared API ── Decision workflow ── SQLite
Manager workspace ┘                       │
                                         ├── Business rules
                                         ├── Local language model
                                         └── Channel adapters
                                              ├── Simulator
                                              ├── Gmail       (planned)
                                              ├── WhatsApp    (planned)
                                              └── Voice       (planned)
```

The shared API connects both frontends to the SQLite workflow. Qwen performs
classification and drafting through Ollama, with a deterministic fallback.
Manager-approved responses are delivered through the configurable outbound
Gmail adapter, which defaults to safe simulation mode.

## Technology

- React
- TypeScript
- Vite
- Python
- SQLite
- Ollama with Qwen3 8B planned for local agent inference
- Faster Whisper planned for local speech transcription

## Run the applications

Requirements:

- Node.js 20 or later
- Python 3.11 or later

Install the frontend dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

In a second terminal, start the backend API:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
.venv/Scripts/python -m uvicorn backend.api.main:app --reload --port 8000
```

Open:

- Customer portal: `http://127.0.0.1:5173/`
- Manager workspace: `http://127.0.0.1:5173/manager`

Build the frontend:

```bash
npm run build
```

## Initialize the database

Create and seed the synthetic local database:

```bash
python -m backend.db.seed
```

Inspect the available review cases:

```bash
python -m backend.db.inspect_database
```

Run the focused database test:

```bash
python -m unittest backend.tests.test_database
```

See [backend/README.md](backend/README.md) for database details.

## Exercise boundary

SAGE currently uses synthetic exercise data. WhatsApp, Gmail, booking, and voice
integrations are simulated. No real customer is contacted, no real appointment
is changed, and no simulated status should be treated as an official dealership
confirmation.

## Roadmap

- Add deeper multilingual evaluation and response drafting.
- Add deterministic decision rules and risk levels.
- Add local speech-to-text and text-to-speech.
- Introduce Gmail and WhatsApp adapters after the simulated workflow is stable.

## License

SAGE is available under the [MIT License](LICENSE).
