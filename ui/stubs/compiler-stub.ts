/**
 * Compiler Service stub. Returns fixture responses for the contract defined in Issue 1.
 *
 * Run: `tsx stubs/compiler-stub.ts`  (port 8001 by default).
 */
import express, { type Request, type Response } from "express";
import cors from "cors";
import { stringify as yamlStringify } from "yaml";
import { FIXTURES, pickFixture } from "./fixtures/inspections";
import type {
  Camera,
  Channel,
  Intent,
  Question,
  Rule,
  Session,
  SessionStatus,
} from "../src/lib/types";

interface SessionState {
  session_id: string;
  status: SessionStatus;
  created_at: string;
  updated_at: string;
  paragraphs: string[];
  title: string;
  intents: Intent[];
  intents_approved: boolean;
  questions: Question[];
  questions_approved: boolean;
  rules: Rule[];
  rules_approved: boolean;
  cameras: Camera[];
  channels: Channel[];
  downstream_stale: { intents: boolean; questions: boolean; rules: boolean };
  fixture_index: number;
  committed?: { customer: string; inspection_id: string; version: number; sha256: string };
}

const sessions = new Map<string, SessionState>();

function newId(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function maskRtsp(url: string): string {
  try {
    const u = new URL(url);
    const host = u.host || "***";
    return `${u.protocol}//${host}${u.pathname}`;
  } catch {
    return url.length > 8 ? `${url.slice(0, 6)}…${url.slice(-3)}` : "***";
  }
}

function maskUrl(url: string): string {
  try {
    const u = new URL(url);
    const host = u.host || "***";
    const tail = u.pathname.split("/").slice(-1)[0] || "";
    return `${u.protocol}//${host}/…/${tail.slice(0, 4)}***`;
  } catch {
    return "***";
  }
}

function touch(s: SessionState) {
  s.updated_at = new Date().toISOString();
}

function asListItem(s: SessionState) {
  return {
    session_id: s.session_id,
    status: s.status,
    created_at: s.created_at,
    updated_at: s.updated_at,
    title: s.title,
  };
}

function ensureSession(req: Request, res: Response): SessionState | null {
  const id = (req.params as { id: string }).id;
  const s = sessions.get(id);
  if (!s) {
    res.status(404).json({ error: `unknown session ${id}` });
    return null;
  }
  return s;
}

const app = express();
app.use(cors());
app.use(express.json({ limit: "1mb" }));

// ---------- sessions ----------
app.get("/sessions", (_req, res) => {
  res.json({ sessions: Array.from(sessions.values()).map(asListItem) });
});

app.post("/sessions", (req, res) => {
  const paragraphs: string[] = Array.isArray(req.body?.paragraphs) ? req.body.paragraphs : [];
  if (paragraphs.length === 0) {
    res.status(400).json({ error: "paragraphs required" });
    return;
  }
  const fixture = pickFixture(paragraphs);
  const fixtureIndex = FIXTURES.indexOf(fixture);
  const id = newId("sess");
  const now = new Date().toISOString();
  const s: SessionState = {
    session_id: id,
    status: "intents_ready",
    created_at: now,
    updated_at: now,
    paragraphs,
    title: fixture.title,
    intents: fixture.intents.map((i) => ({ ...i })),
    intents_approved: false,
    questions: [],
    questions_approved: false,
    rules: [],
    rules_approved: false,
    cameras: [],
    channels: [],
    downstream_stale: { intents: false, questions: false, rules: false },
    fixture_index: fixtureIndex,
  };
  sessions.set(id, s);
  res.status(201).json({ session_id: id, status: s.status });
});

app.get("/sessions/:id", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const session: Session = {
    session_id: s.session_id,
    status: s.status,
    created_at: s.created_at,
    updated_at: s.updated_at,
    paragraph_count: s.paragraphs.length,
    downstream_stale: s.downstream_stale,
  };
  res.json(session);
});

// ---------- intents ----------
app.get("/sessions/:id/intents", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  res.json({
    intents: s.intents,
    downstream_stale: s.downstream_stale.questions || s.downstream_stale.rules,
  });
});

app.put("/sessions/:id/intents/:idx", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const idx = Number(req.params.idx);
  const intent = s.intents.find((i) => i.idx === idx);
  if (!intent) {
    res.status(404).json({ error: "intent not found" });
    return;
  }
  Object.assign(intent, req.body ?? {});
  if (s.intents_approved) {
    s.downstream_stale.questions = true;
    s.downstream_stale.rules = true;
  }
  touch(s);
  res.json({ intent, downstream_stale: s.downstream_stale.questions });
});

app.delete("/sessions/:id/intents/:idx", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const idx = Number(req.params.idx);
  s.intents = s.intents.filter((i) => i.idx !== idx).map((i, n) => ({ ...i, idx: n }));
  if (s.intents_approved) {
    s.downstream_stale.questions = true;
    s.downstream_stale.rules = true;
  }
  touch(s);
  res.json({ ok: true });
});

app.post("/sessions/:id/intents/:idx/regenerate", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const idx = Number(req.params.idx);
  const intent = s.intents.find((i) => i.idx === idx);
  if (!intent) {
    res.status(404).json({ error: "intent not found" });
    return;
  }
  const hint: string | undefined = req.body?.hint ?? undefined;
  intent.original_text = hint
    ? `${intent.original_text} [hint: ${hint}]`
    : intent.original_text;
  intent.entity = `${intent.entity} (regen)`;
  if (s.intents_approved) {
    s.downstream_stale.questions = true;
    s.downstream_stale.rules = true;
  }
  touch(s);
  res.json({ intent });
});

app.post("/sessions/:id/intents/approve", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const fixture = FIXTURES[s.fixture_index];
  s.questions = fixture.questions
    .filter((q) => s.intents.some((i) => i.idx === q.intent_idx))
    .map((q, n) => ({ ...q, idx: n }));
  s.intents_approved = true;
  s.questions_approved = false;
  s.rules = [];
  s.rules_approved = false;
  s.status = "questions_ready";
  s.downstream_stale.questions = false;
  s.downstream_stale.rules = true;
  touch(s);
  res.json({ status: s.status, intent_count: s.intents.length });
});

// ---------- questions ----------
app.get("/sessions/:id/questions", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  res.json({ questions: s.questions, downstream_stale: s.downstream_stale.rules });
});

app.put("/sessions/:id/questions/:idx", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const idx = Number(req.params.idx);
  const q = s.questions.find((x) => x.idx === idx);
  if (!q) {
    res.status(404).json({ error: "question not found" });
    return;
  }
  Object.assign(q, req.body ?? {});
  if (s.questions_approved) s.downstream_stale.rules = true;
  touch(s);
  res.json({ question: q, downstream_stale: s.downstream_stale.rules });
});

app.post("/sessions/:id/questions/:idx/regenerate", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const idx = Number(req.params.idx);
  const q = s.questions.find((x) => x.idx === idx);
  if (!q) {
    res.status(404).json({ error: "question not found" });
    return;
  }
  const hint: string | undefined = req.body?.hint ?? undefined;
  q.prompt = hint ? `${q.prompt}\n\n# Regenerated with hint: ${hint}` : `${q.prompt}\n# regen`;
  if (s.questions_approved) s.downstream_stale.rules = true;
  touch(s);
  res.json({ question: q });
});

app.post("/sessions/:id/questions/approve", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const fixture = FIXTURES[s.fixture_index];
  s.rules = fixture.rules
    .filter((r) => s.questions.some((q) => q.idx === r.question_idx))
    .map((r, n) => ({ ...r, idx: n }));
  s.questions_approved = true;
  s.rules_approved = false;
  s.status = "rules_ready";
  s.downstream_stale.rules = false;
  touch(s);
  res.json({ status: s.status, question_count: s.questions.length });
});

// ---------- rules ----------
app.get("/sessions/:id/rules", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  res.json({ rules: s.rules });
});

app.put("/sessions/:id/rules/:idx", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const idx = Number(req.params.idx);
  const r = s.rules.find((x) => x.idx === idx);
  if (!r) {
    res.status(404).json({ error: "rule not found" });
    return;
  }
  Object.assign(r, req.body ?? {});
  touch(s);
  res.json({ rule: r });
});

app.post("/sessions/:id/rules/approve", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  s.rules_approved = true;
  s.status = "ready_for_config";
  touch(s);
  res.json({ status: s.status });
});

// ---------- cameras ----------
app.get("/sessions/:id/cameras", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  res.json({ cameras: s.cameras });
});

app.post("/sessions/:id/cameras", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const { name, rtsp_url, timezone } = req.body ?? {};
  if (!name || !rtsp_url || !timezone) {
    res.status(400).json({ error: "name, rtsp_url, timezone required" });
    return;
  }
  const camera: Camera = {
    id: newId("cam"),
    name,
    rtsp_secret_ref: `secret/${newId("rtsp").replace("_", "/")}`,
    timezone,
    rtsp_url_masked: maskRtsp(rtsp_url),
  };
  s.cameras.push(camera);
  touch(s);
  res.status(201).json({ camera });
});

app.delete("/sessions/:id/cameras/:cameraId", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  s.cameras = s.cameras.filter((c) => c.id !== req.params.cameraId);
  touch(s);
  res.json({ ok: true });
});

// ---------- channels ----------
app.get("/sessions/:id/channels", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  res.json({ channels: s.channels });
});

app.post("/sessions/:id/channels", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const { type, name, url } = req.body ?? {};
  if (!type || !name || !url) {
    res.status(400).json({ error: "type, name, url required" });
    return;
  }
  const channel: Channel = {
    id: newId("ch"),
    type,
    name,
    secret_ref: `secret/${newId("ch").replace("_", "/")}`,
    url_masked: maskUrl(url),
  };
  s.channels.push(channel);
  touch(s);
  res.status(201).json({ channel });
});

app.delete("/sessions/:id/channels/:channelId", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  s.channels = s.channels.filter((c) => c.id !== req.params.channelId);
  touch(s);
  res.json({ ok: true });
});

app.post("/sessions/:id/channels/:channelId/test", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const ch = s.channels.find((c) => c.id === req.params.channelId);
  if (!ch) {
    res.status(404).json({ error: "channel not found" });
    return;
  }
  res.json({ ok: true, message: `Test ping delivered to ${ch.name}.` });
});

// ---------- DSL / validate / commit ----------
function buildDsl(s: SessionState): unknown {
  return {
    apiVersion: "vid-insp/v1",
    kind: "Inspection",
    metadata: { title: s.title, session_id: s.session_id },
    cameras: s.cameras.map((c) => ({
      id: c.id,
      name: c.name,
      timezone: c.timezone,
      rtsp_secret_ref: c.rtsp_secret_ref,
    })),
    questions: s.questions.map((q) => ({
      id: `q_${q.idx}`,
      target: q.target,
      sample_every: q.sample_every,
      prompt: q.prompt,
      output_schema: q.output_schema,
    })),
    rules: s.rules.map((r) => ({
      id: r.rule_id,
      on: { question: `q_${r.question_idx}` },
      when: r.expression,
      sustained_for: r.sustained_for,
      sustained_threshold: r.sustained_threshold,
      cooldown: r.cooldown,
      severity: r.severity,
      message: r.message,
    })),
    channels: s.channels.map((c) => ({
      id: c.id,
      type: c.type,
      name: c.name,
      secret_ref: c.secret_ref,
    })),
  };
}

app.get("/sessions/:id/dsl", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  res.type("application/x-yaml").send(yamlStringify(buildDsl(s)));
});

app.post("/sessions/:id/validate", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const g1: string[] = [];
  const g2: string[] = [];
  for (const r of s.rules) {
    if (!s.questions.find((q) => q.idx === r.question_idx)) {
      g1.push(`rules[${r.idx}].on.question references unknown question_idx ${r.question_idx}`);
    }
  }
  if (s.cameras.length === 0) g2.push("no cameras configured");
  if (s.channels.length === 0) g2.push("no alert channels configured");
  res.json({ valid: g1.length === 0 && g2.length === 0, g1_errors: g1, g2_errors: g2 });
});

app.post("/sessions/:id/commit", (req, res) => {
  const s = ensureSession(req, res);
  if (!s) return;
  const payload = JSON.stringify(buildDsl(s));
  let h = 0;
  for (let i = 0; i < payload.length; i++) h = (h * 31 + payload.charCodeAt(i)) | 0;
  const sha = (h >>> 0).toString(16).padStart(8, "0").repeat(8).slice(0, 64);
  s.committed = {
    customer: "cust_1",
    inspection_id: s.session_id.replace("sess_", "insp_"),
    version: (s.committed?.version ?? 0) + 1,
    sha256: sha,
  };
  s.status = "committed";
  touch(s);
  res.status(201).json({ registry_ref: s.committed });
});

const port = Number(process.env.COMPILER_STUB_PORT || 8001);
app.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`[compiler-stub] listening on http://localhost:${port}`);
});
