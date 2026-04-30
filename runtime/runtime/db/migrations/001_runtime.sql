-- 001_runtime.sql — observation log, alert history, hourly cost snapshots.

CREATE TABLE IF NOT EXISTS observations (
    id            BIGSERIAL PRIMARY KEY,
    deployment_id TEXT NOT NULL,
    camera_id     TEXT NOT NULL,
    question_id   TEXT NOT NULL,
    timestamp     TIMESTAMPTZ NOT NULL,
    answer        JSONB,
    confidence    FLOAT,
    is_gap        BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_obs_camera_ts
    ON observations (camera_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_obs_deployment_ts
    ON observations (deployment_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS alert_history (
    id                   BIGSERIAL PRIMARY KEY,
    deployment_id        TEXT NOT NULL,
    rule_id              TEXT NOT NULL,
    camera_id            TEXT NOT NULL,
    severity             TEXT NOT NULL,
    message              TEXT,
    violator_description TEXT,
    vote_ratio           FLOAT,
    payload              JSONB,
    dispatched_at        TIMESTAMPTZ NOT NULL,
    created_at           TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_alerts_deployment_ts
    ON alert_history (deployment_id, dispatched_at DESC);

CREATE TABLE IF NOT EXISTS cost_snapshots (
    id            BIGSERIAL PRIMARY KEY,
    deployment_id TEXT NOT NULL,
    camera_id     TEXT NOT NULL,
    question_id   TEXT NOT NULL,
    hour          TIMESTAMPTZ NOT NULL,
    call_count    INTEGER NOT NULL,
    cost_usd      FLOAT NOT NULL,
    UNIQUE (deployment_id, camera_id, question_id, hour)
);
