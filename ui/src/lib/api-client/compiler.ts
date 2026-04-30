import type {
  CommitResult,
  Intent,
  Question,
  Rule,
  Camera,
  Channel,
  Session,
  SessionListItem,
  ValidationResult,
} from "@/lib/types";
import { request, requestText } from "./http";

const BASE = "/api/compiler";

export const compiler = {
  // ---------- sessions ----------
  listSessions(): Promise<{ sessions: SessionListItem[] }> {
    return request(`${BASE}/sessions`);
  },

  createSession(paragraphs: string[]): Promise<{ session_id: string; status: string }> {
    return request(`${BASE}/sessions`, {
      method: "POST",
      body: JSON.stringify({ paragraphs }),
    });
  },

  getSession(id: string): Promise<Session> {
    return request(`${BASE}/sessions/${id}`);
  },

  // ---------- intents ----------
  listIntents(id: string): Promise<{ intents: Intent[]; downstream_stale: boolean }> {
    return request(`${BASE}/sessions/${id}/intents`);
  },

  updateIntent(
    id: string,
    idx: number,
    patch: Partial<Intent>,
  ): Promise<{ intent: Intent; downstream_stale: boolean }> {
    return request(`${BASE}/sessions/${id}/intents/${idx}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    });
  },

  deleteIntent(id: string, idx: number): Promise<{ ok: true }> {
    return request(`${BASE}/sessions/${id}/intents/${idx}`, { method: "DELETE" });
  },

  regenerateIntent(id: string, idx: number, hint?: string): Promise<{ intent: Intent }> {
    return request(`${BASE}/sessions/${id}/intents/${idx}/regenerate`, {
      method: "POST",
      body: JSON.stringify({ hint: hint ?? null }),
    });
  },

  approveIntents(id: string): Promise<{ status: string; intent_count: number }> {
    return request(`${BASE}/sessions/${id}/intents/approve`, { method: "POST" });
  },

  // ---------- questions ----------
  listQuestions(id: string): Promise<{ questions: Question[]; downstream_stale: boolean }> {
    return request(`${BASE}/sessions/${id}/questions`);
  },

  updateQuestion(
    id: string,
    idx: number,
    patch: Partial<Question>,
  ): Promise<{ question: Question; downstream_stale: boolean }> {
    return request(`${BASE}/sessions/${id}/questions/${idx}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    });
  },

  regenerateQuestion(id: string, idx: number, hint?: string): Promise<{ question: Question }> {
    return request(`${BASE}/sessions/${id}/questions/${idx}/regenerate`, {
      method: "POST",
      body: JSON.stringify({ hint: hint ?? null }),
    });
  },

  approveQuestions(id: string): Promise<{ status: string; question_count: number }> {
    return request(`${BASE}/sessions/${id}/questions/approve`, { method: "POST" });
  },

  // ---------- rules ----------
  listRules(id: string): Promise<{ rules: Rule[] }> {
    return request(`${BASE}/sessions/${id}/rules`);
  },

  updateRule(id: string, idx: number, patch: Partial<Rule>): Promise<{ rule: Rule }> {
    return request(`${BASE}/sessions/${id}/rules/${idx}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    });
  },

  approveRules(id: string): Promise<{ status: string }> {
    return request(`${BASE}/sessions/${id}/rules/approve`, { method: "POST" });
  },

  // ---------- cameras ----------
  listCameras(id: string): Promise<{ cameras: Camera[] }> {
    return request(`${BASE}/sessions/${id}/cameras`);
  },

  addCamera(
    id: string,
    body: { name: string; rtsp_url: string; timezone: string },
  ): Promise<{ camera: Camera }> {
    return request(`${BASE}/sessions/${id}/cameras`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  deleteCamera(id: string, cameraId: string): Promise<{ ok: true }> {
    return request(`${BASE}/sessions/${id}/cameras/${cameraId}`, { method: "DELETE" });
  },

  // ---------- channels ----------
  listChannels(id: string): Promise<{ channels: Channel[] }> {
    return request(`${BASE}/sessions/${id}/channels`);
  },

  addChannel(
    id: string,
    body: { type: "slack" | "pagerduty" | "webhook"; name: string; url: string },
  ): Promise<{ channel: Channel }> {
    return request(`${BASE}/sessions/${id}/channels`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  deleteChannel(id: string, channelId: string): Promise<{ ok: true }> {
    return request(`${BASE}/sessions/${id}/channels/${channelId}`, { method: "DELETE" });
  },

  testChannel(id: string, channelId: string): Promise<{ ok: boolean; message: string }> {
    return request(`${BASE}/sessions/${id}/channels/${channelId}/test`, { method: "POST" });
  },

  // ---------- DSL / commit ----------
  getDsl(id: string): Promise<string> {
    return requestText(`${BASE}/sessions/${id}/dsl`, {
      headers: { Accept: "application/x-yaml" },
    });
  },

  validate(id: string): Promise<ValidationResult> {
    return request(`${BASE}/sessions/${id}/validate`, { method: "POST" });
  },

  commit(id: string): Promise<CommitResult> {
    return request(`${BASE}/sessions/${id}/commit`, { method: "POST" });
  },
};
