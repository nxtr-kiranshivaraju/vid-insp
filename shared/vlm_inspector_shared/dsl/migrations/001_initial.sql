-- Registry tables shared by the compiler (writer) and the runtime (reader).
-- Owned by the shared package because both services need the schema contract.

CREATE TABLE IF NOT EXISTS dsl_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     TEXT NOT NULL,
    inspection_id   TEXT NOT NULL,
    version         INTEGER NOT NULL,
    sha256          TEXT NOT NULL,
    dsl             JSONB NOT NULL,
    committed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (customer_id, inspection_id, version)
);
CREATE INDEX IF NOT EXISTS idx_dsl_registry_customer_inspection
    ON dsl_registry (customer_id, inspection_id, version DESC);

-- ARCH-4: RTSP URLs and webhook URLs are stored separately from the DSL.
-- LLM/VLM API keys are NEVER stored here — they are env-only on the runtime
-- and compiler containers.
CREATE TABLE IF NOT EXISTS secrets (
    id          TEXT PRIMARY KEY,           -- e.g., cam_loading_bay_rtsp, slack_safety
    customer_id TEXT NOT NULL,
    secret_type TEXT NOT NULL,              -- rtsp_url | webhook_url
    value       TEXT NOT NULL,              -- encrypted at rest at the application layer
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
