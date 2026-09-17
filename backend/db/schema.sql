PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    preferred_language TEXT NOT NULL,
    contact_permission TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vehicles (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    registration_normalized TEXT NOT NULL UNIQUE,
    make TEXT,
    model TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS service_jobs (
    id TEXT PRIMARY KEY,
    vehicle_id TEXT NOT NULL REFERENCES vehicles(id),
    appointment_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_status_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES service_jobs(id),
    source TEXT NOT NULL,
    status_type TEXT NOT NULL,
    status_value TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    raw_payload_json TEXT,
    UNIQUE(job_id, source, status_type, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_job_status_events_job
    ON job_status_events(job_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    job_id TEXT REFERENCES service_jobs(id),
    state TEXT NOT NULL CHECK(state IN (
        'OPEN', 'CHECKING_RECORDS', 'WAITING_HUMAN_REVIEW',
        'RESPONSE_APPROVED', 'RESOLVED'
    )),
    delivery_email TEXT,
    email_consent_at TEXT,
    opened_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_conversations_customer
    ON conversations(customer_id, opened_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    external_message_id TEXT UNIQUE,
    channel TEXT NOT NULL CHECK(channel IN (
        'SIMULATOR', 'WHATSAPP', 'GMAIL', 'VOICE', 'PHONE_NOTE', 'WEB_CHAT'
    )),
    direction TEXT NOT NULL CHECK(direction IN ('INBOUND', 'OUTBOUND')),
    content TEXT NOT NULL,
    language TEXT,
    delivery_status TEXT NOT NULL CHECK(delivery_status IN (
        'RECEIVED', 'DRAFT', 'APPROVED', 'SIMULATED', 'SENT', 'FAILED'
    )),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS classifications (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE REFERENCES messages(id),
    intent TEXT NOT NULL CHECK(intent IN (
        'COLLECTION_STATUS', 'REPAIR_STATUS', 'BOOKING_CHANGE',
        'REPEATED_ENQUIRY', 'GENERAL_REQUEST'
    )),
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    extracted_entities_json TEXT NOT NULL DEFAULT '{}',
    model_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE REFERENCES messages(id),
    outcome TEXT NOT NULL CHECK(outcome IN (
        'ANSWER', 'CALLBACK', 'NEEDS_REVIEW', 'INSUFFICIENT_EVIDENCE'
    )),
    justification TEXT NOT NULL,
    proposed_response TEXT NOT NULL,
    rules_triggered_json TEXT NOT NULL DEFAULT '[]',
    rule_version TEXT NOT NULL,
    model_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    captured_value TEXT NOT NULL,
    observed_at TEXT,
    UNIQUE(decision_id, source_type, source_record_id, field_name)
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL UNIQUE REFERENCES decisions(id),
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'APPROVED', 'CORRECTED', 'REJECTED')),
    reviewer_id TEXT,
    final_response TEXT,
    reviewer_note TEXT,
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_reviews_status
    ON reviews(status, created_at DESC);

CREATE TABLE IF NOT EXISTS channel_connections (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL UNIQUE CHECK(channel IN ('WHATSAPP', 'GMAIL', 'VOICE')),
    status TEXT NOT NULL CHECK(status IN ('NOT_CONNECTED', 'CONNECTED', 'PLANNED')),
    account_label TEXT,
    configuration_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_type TEXT NOT NULL CHECK(actor_type IN ('CUSTOMER', 'AGENT', 'MANAGER', 'SYSTEM')),
    actor_id TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_events_entity
    ON audit_events(entity_type, entity_id, created_at DESC);
