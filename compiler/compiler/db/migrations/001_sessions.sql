-- Compiler-side sessions table. The shared dsl_registry + secrets tables are
-- created by shared/dsl/migrations/001_initial.sql and must run first.

CREATE TABLE IF NOT EXISTS sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status          TEXT NOT NULL DEFAULT 'created',
    paragraphs      JSONB NOT NULL,
    intents         JSONB,
    intents_approved BOOLEAN NOT NULL DEFAULT FALSE,
    questions       JSONB,
    questions_approved BOOLEAN NOT NULL DEFAULT FALSE,
    rules           JSONB,
    rules_approved  BOOLEAN NOT NULL DEFAULT FALSE,
    cameras         JSONB,
    channels        JSONB,
    dsl             JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions (updated_at);
