import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

// Use a wildcard scheme/host so handlers match both bare paths
// (rewritten by tests/setup.ts) and any absolute URL.
const u = (path: string) => `*${path}`;

export const handlers = [
  // ------- compiler proxy routes -------
  http.post(u("/api/compiler/sessions"), async () => {
    return HttpResponse.json({ session_id: "sess_test", status: "intents_ready" }, { status: 201 });
  }),

  http.get(u("/api/compiler/sessions/sess_test/intents"), () => {
    return HttpResponse.json({
      intents: [
        {
          idx: 0,
          check_type: "presence_required",
          entity: "hard hat",
          location: "loading bay",
          required: true,
          schedule: null,
          severity: "high",
          original_text: "Workers must wear hard hats.",
        },
      ],
      downstream_stale: false,
    });
  }),

  http.post(u("/api/compiler/sessions/sess_test/intents/approve"), () => {
    return HttpResponse.json({ status: "questions_ready", intent_count: 1 });
  }),

  http.get(u("/api/compiler/sessions/sess_test/dsl"), () => {
    return new HttpResponse("apiVersion: vid-insp/v1\nkind: Inspection\n", {
      headers: { "Content-Type": "application/x-yaml" },
    });
  }),

  http.post(u("/api/compiler/sessions/sess_test/validate"), () => {
    return HttpResponse.json({ valid: true, g1_errors: [], g2_errors: [] });
  }),

  // ------- runtime proxy routes -------
  http.post(u("/api/runtime/probe"), async ({ request }) => {
    const body = (await request.json()) as { rtsp_url?: string };
    const ok = !!body.rtsp_url?.startsWith("rtsp://");
    return HttpResponse.json(
      ok ? { ok: true, message: "Connected" } : { ok: false, message: "bad url" },
    );
  }),
];

export const server = setupServer(...handlers);
