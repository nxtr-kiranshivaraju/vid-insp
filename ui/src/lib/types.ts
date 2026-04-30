export type Severity = "low" | "medium" | "high" | "critical";

export type CheckType =
  | "presence_required"
  | "presence_forbidden"
  | "count_threshold"
  | "behavior"
  | "interaction"
  | "state";

export interface Intent {
  idx: number;
  check_type: CheckType;
  entity: string;
  location: string | null;
  required: boolean;
  schedule: string | null;
  severity: Severity;
  original_text: string;
}

export interface OutputSchema {
  type: "object";
  properties: Record<string, { type: string; minimum?: number; maximum?: number; description?: string }>;
  required: string[];
}

export interface Question {
  idx: number;
  intent_idx: number;
  prompt: string;
  output_schema: OutputSchema;
  target: "full_frame" | "crop";
  sample_every: string;
}

export interface Rule {
  idx: number;
  question_idx: number;
  rule_id: string;
  expression: string;
  sustained_for: string;
  sustained_threshold: number;
  cooldown: string;
  severity: Severity;
  message: string;
}

export interface Camera {
  id: string;
  name: string;
  rtsp_secret_ref: string;
  timezone: string;
  rtsp_url_masked: string;
}

export type ChannelType = "slack" | "pagerduty" | "webhook";

export interface Channel {
  id: string;
  type: ChannelType;
  name: string;
  secret_ref: string;
  url_masked: string;
}

export type SessionStatus =
  | "intents_ready"
  | "questions_ready"
  | "rules_ready"
  | "ready_for_config"
  | "committed";

export interface Session {
  session_id: string;
  status: SessionStatus;
  created_at: string;
  updated_at: string;
  paragraph_count: number;
  downstream_stale?: { intents?: boolean; questions?: boolean; rules?: boolean };
}

export interface SessionListItem {
  session_id: string;
  status: SessionStatus;
  created_at: string;
  updated_at: string;
  title: string;
}

export interface ValidationResult {
  valid: boolean;
  g1_errors: string[];
  g2_errors: string[];
}

export interface CommitResult {
  registry_ref: {
    customer: string;
    inspection_id: string;
    version: number;
    sha256: string;
  };
}

export interface RuntimeStatus {
  state: "preflight" | "running" | "paused" | "error";
  uptime_seconds: number;
  dsl_version: number;
  cameras_active: number;
  cameras_failed: number;
}

export interface Alert {
  id: string;
  timestamp: string;
  camera_id: string;
  rule_id: string;
  severity: Severity;
  message: string;
  violator_description: string | null;
  snapshot_url: string;
}

export interface CostSummary {
  rolling_hour_usd: number;
  rolling_day_usd: number;
  by_camera: Record<string, number>;
  by_question?: Record<string, number>;
  budget_threshold_usd?: number;
}

export type CameraHealthStatus = "ok" | "backoff" | "failed";

export interface CameraHealth {
  status: CameraHealthStatus;
  retry_count: number;
  last_frame: string | null;
  observation_count?: number;
  last_alert_at?: string | null;
  thumbnail_url?: string | null;
}

export interface HealthSummary {
  cameras: Record<string, CameraHealth>;
  vlm_coercion_errors: Record<string, Record<string, number>>;
  observation_gaps: Record<string, number>;
}

export interface ProbeResult {
  ok: boolean;
  message: string;
  resolution?: string;
  fps?: number;
}
