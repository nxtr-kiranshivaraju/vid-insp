import { describe, expect, it } from "vitest";
import { compiler } from "@/lib/api-client/compiler";
import { runtime } from "@/lib/api-client/runtime";

// jsdom resolves relative URLs against http://localhost/. MSW handlers use a wildcard
// origin (`*/api/...`) so they match both that and any absolute origin.

describe("compiler client", () => {
  it("creates a session", async () => {
    const res = await compiler.createSession(["Workers must wear hard hats."]);
    expect(res.session_id).toBe("sess_test");
    expect(res.status).toBe("intents_ready");
  });

  it("lists intents", async () => {
    const res = await compiler.listIntents("sess_test");
    expect(res.intents).toHaveLength(1);
    expect(res.intents[0].entity).toBe("hard hat");
    expect(res.downstream_stale).toBe(false);
  });

  it("approves intents", async () => {
    const res = await compiler.approveIntents("sess_test");
    expect(res.status).toBe("questions_ready");
    expect(res.intent_count).toBe(1);
  });

  it("returns DSL as YAML text", async () => {
    const yaml = await compiler.getDsl("sess_test");
    expect(yaml).toContain("apiVersion: vid-insp/v1");
  });

  it("validates", async () => {
    const r = await compiler.validate("sess_test");
    expect(r.valid).toBe(true);
    expect(r.g1_errors).toEqual([]);
  });
});

describe("runtime client", () => {
  it("probes RTSP", async () => {
    const ok = await runtime.probe("rtsp://cam.local/stream");
    expect(ok.ok).toBe(true);

    const bad = await runtime.probe("http://nope");
    expect(bad.ok).toBe(false);
  });
});
