/**
 * Runtime Service stub. Read-only fixtures for the monitor screen, plus a /probe and
 * deployment lifecycle endpoint set used by the wizard's Step 5 / Step 8.
 *
 * Run: `tsx stubs/runtime-stub.ts`  (port 8002 by default).
 */
import express, { type Request, type Response } from "express";
import cors from "cors";
import type {
  Alert,
  CostSummary,
  HealthSummary,
  RuntimeStatus,
} from "../src/lib/types";

interface DeploymentState {
  deployment_id: string;
  state: RuntimeStatus["state"];
  started_at: number;
  dsl_version: number;
  cameras: string[];
  preflight_done: boolean;
}

const deployments = new Map<string, DeploymentState>();

function ensure(req: Request, res: Response): DeploymentState | null {
  const id = (req.params as { deployment_id: string }).deployment_id;
  const dep = deployments.get(id);
  if (!dep) {
    res.status(404).json({ error: `unknown deployment ${id}` });
    return null;
  }
  return dep;
}

const app = express();
app.use(cors());
app.use(express.json({ limit: "1mb" }));

app.post("/probe", (req, res) => {
  const url: string = req.body?.rtsp_url ?? "";
  if (!url) {
    res.status(400).json({ ok: false, message: "rtsp_url required" });
    return;
  }
  const ok = /^rtsp(s)?:\/\//i.test(url);
  res.json(
    ok
      ? { ok: true, message: "Connected", resolution: "1920x1080", fps: 25 }
      : { ok: false, message: "Not a valid rtsp:// URL" },
  );
});

app.post("/deployments", (req, res) => {
  const ref = req.body?.registry_ref;
  const id = `dep_${Math.random().toString(36).slice(2, 10)}`;
  const dep: DeploymentState = {
    deployment_id: id,
    state: "preflight",
    started_at: Date.now(),
    dsl_version: ref?.version ?? 1,
    cameras: ["cam_loading_bay", "cam_dock_west", "cam_dock_east"],
    preflight_done: false,
  };
  deployments.set(id, dep);
  res.status(201).json({ deployment_id: id, state: dep.state });
});

app.post("/deployments/:deployment_id/preflight", (req, res) => {
  const dep = ensure(req, res);
  if (!dep) return;
  dep.preflight_done = true;
  res.json({
    gates: [
      { name: "G3_dsl_signature", status: "pass", detail: "DSL SHA matches registry." },
      { name: "G4_cost_estimate", status: "pass", detail: "Estimated $0.42/hr — within budget." },
      { name: "G5_camera_connectivity", status: "pass", detail: "All cameras reachable." },
      {
        name: "G6_vlm_smoke",
        status: "pass",
        detail: "Sample VLM call returned a schema-valid response.",
      },
      { name: "G7_alert_channels", status: "pass", detail: "All alert channels acked test ping." },
    ],
  });
});

app.post("/deployments/:deployment_id/go-live", (req, res) => {
  const dep = ensure(req, res);
  if (!dep) return;
  if (!dep.preflight_done) {
    res.status(409).json({ error: "preflight not run" });
    return;
  }
  dep.state = "running";
  dep.started_at = Date.now();
  res.json({ state: dep.state });
});

app.get("/deployments/:deployment_id/status", (req, res) => {
  const dep = ensure(req, res);
  if (!dep) return;
  const status: RuntimeStatus = {
    state: dep.state,
    uptime_seconds: Math.max(0, Math.floor((Date.now() - dep.started_at) / 1000)),
    dsl_version: dep.dsl_version,
    cameras_active: dep.cameras.length,
    cameras_failed: 0,
  };
  res.json(status);
});

const ALERT_FIXTURES: Alert[] = [
  {
    id: "alert_001",
    timestamp: new Date(Date.now() - 60_000).toISOString(),
    camera_id: "cam_loading_bay",
    rule_id: "rule_hardhat",
    severity: "high",
    message: "Hard hat violation in Loading Bay",
    violator_description: "Person in red jacket near second forklift, no hard hat visible.",
    snapshot_url: "https://placehold.co/320x180/png?text=alert_001",
  },
  {
    id: "alert_002",
    timestamp: new Date(Date.now() - 360_000).toISOString(),
    camera_id: "cam_dock_west",
    rule_id: "rule_forklift_proximity",
    severity: "critical",
    message: "Forklift within 3m of pedestrian",
    violator_description: "Forklift A approached worker in blue overalls at 2.1m.",
    snapshot_url: "https://placehold.co/320x180/png?text=alert_002",
  },
  {
    id: "alert_003",
    timestamp: new Date(Date.now() - 1_500_000).toISOString(),
    camera_id: "cam_loading_bay",
    rule_id: "rule_vest",
    severity: "medium",
    message: "Hi-vis vest violation",
    violator_description: "Worker in dark hoodie by pallet stack 3.",
    snapshot_url: "https://placehold.co/320x180/png?text=alert_003",
  },
];

app.get("/deployments/:deployment_id/alerts", (req, res) => {
  const dep = ensure(req, res);
  if (!dep) return;
  const sev = (req.query.severity as string | undefined)?.toLowerCase();
  const limit = Number(req.query.limit ?? 50);
  let alerts = ALERT_FIXTURES;
  if (sev) alerts = alerts.filter((a) => a.severity === sev);
  res.json({ alerts: alerts.slice(0, limit) });
});

app.get("/deployments/:deployment_id/cost", (req, res) => {
  const dep = ensure(req, res);
  if (!dep) return;
  const cost: CostSummary = {
    rolling_hour_usd: 0.42,
    rolling_day_usd: 8.1,
    by_camera: {
      cam_loading_bay: 0.18,
      cam_dock_west: 0.14,
      cam_dock_east: 0.1,
    },
    budget_threshold_usd: 0.5,
  };
  res.json(cost);
});

app.get("/deployments/:deployment_id/health", (req, res) => {
  const dep = ensure(req, res);
  if (!dep) return;
  const now = new Date().toISOString();
  const health: HealthSummary = {
    cameras: {
      cam_loading_bay: {
        status: "ok",
        retry_count: 0,
        last_frame: now,
        observation_count: 1234,
        last_alert_at: ALERT_FIXTURES[0].timestamp,
        thumbnail_url: "https://placehold.co/320x180/png?text=cam_loading_bay",
      },
      cam_dock_west: {
        status: "ok",
        retry_count: 0,
        last_frame: now,
        observation_count: 980,
        last_alert_at: ALERT_FIXTURES[1].timestamp,
        thumbnail_url: "https://placehold.co/320x180/png?text=cam_dock_west",
      },
      cam_dock_east: {
        status: "backoff",
        retry_count: 4,
        last_frame: new Date(Date.now() - 90_000).toISOString(),
        observation_count: 612,
        last_alert_at: null,
        thumbnail_url: null,
      },
    },
    vlm_coercion_errors: {
      q_hardhat: { anthropic: 2, openai: 0 },
      q_forklift_proximity: { anthropic: 0, openai: 1 },
    },
    observation_gaps: {
      "cam_loading_bay/q_hardhat": 1,
      "cam_dock_east/q_hardhat": 5,
    },
  };
  res.json(health);
});

const port = Number(process.env.RUNTIME_STUB_PORT || 8002);
app.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`[runtime-stub] listening on http://localhost:${port}`);
});
