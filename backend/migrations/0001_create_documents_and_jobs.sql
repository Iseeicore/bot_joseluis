CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE document_versions (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents (id),
    version_number INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_sha256 TEXT NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (document_id, version_number)
);

CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES document_versions (id),
    request TEXT NOT NULL,
    ocr INTEGER NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'extracting', 'analyzing', 'summarizing', 'completed', 'failed')),
    progress_done INTEGER,
    progress_total INTEGER,
    result_json TEXT,
    error_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX jobs_unfailed_idempotency_key ON jobs (idempotency_key) WHERE status <> 'failed';

CREATE INDEX jobs_status_created_at ON jobs (status, created_at);
