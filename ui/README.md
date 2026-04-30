# Video Inspection — UI (Issue 1)

Next.js 14 (App Router) console for authoring inspection rules in plain English, reviewing
compiler output, configuring cameras and channels, running preflight, and monitoring a
deployment. Calls the Compiler Service (Issue 2) and Runtime Service (Issue 3) over REST.
Both services are stubbed in `stubs/` so the wizard works end-to-end without the real backends.

## Quick start

```bash
cd ui
cp .env.example .env
npm install
npm run dev   # UI on :3000, compiler-stub on :8001, runtime-stub on :8002
```

Open http://localhost:3000 and sign in with the token from `.env` (default `dev-token`).

## Auth

Single-tenant, single user. The `AUTH_TOKEN` env var is checked by `src/middleware.ts`. The
token is placed in an HTTP-only cookie on login (`/api/auth/login`); subsequent requests must
present either `Authorization: Bearer <token>` or the cookie.

## Wizard flow (8 steps)

1. `/inspections/new` — paste paragraphs.
2. `/inspections/:id/intents` — review and edit extracted intents; approve to generate questions.
3. `/inspections/:id/questions` — review prompts and output schemas; ARCH-3 `violator_description` is highlighted as a green badge.
4. `/inspections/:id/rules` — adjust thresholds; ARCH-1 `sustained_threshold` has a hover tooltip.
5. `/inspections/:id/cameras` — add cameras (RTSP URL stored as secret ref, masked after save). The Test connectivity button calls runtime `POST /probe`.
6. `/inspections/:id/channels` — add Slack/PagerDuty/webhook channels (URL masked after save).
7. `/inspections/:id/preview` — read-only YAML; G1/G2 validation badges.
8. `/inspections/:id/deploy` — commit DSL, run preflight (G3–G7), go live.

Editing an upstream layer after approval invalidates downstream and surfaces a "Re-approve to
regenerate" banner.

## Monitor

`/monitor/:deployment_id` polls the runtime every 5 seconds (SWR `refreshInterval: 5000`) and
shows status, camera grid, recent alerts (with violator description), cost meter, and health
panel.

## Stubs

Three fixture inspections are bundled (`stubs/fixtures/inspections.ts`):
warehouse PPE, kitchen hygiene, hospital fall risk. The fixture is selected by simple keyword
matching on the submitted paragraphs.

## Tests

```bash
npm run test            # vitest + MSW unit tests for api-client
npm run test:e2e        # Playwright e2e against the running stubs
```

## Docker

```bash
docker compose up --build
```

Brings up `ui` on :3000 plus the two stubs on :8001 and :8002.

## Architecture notes

- **Proxy pattern**: Browser code calls `/api/compiler/*` and `/api/runtime/*` on the Next.js server, which proxies to `COMPILER_URL` / `RUNTIME_URL`. Keeps the auth boundary single, hides upstream URLs from the browser.
- **No business logic in the UI**: All compilation and validation happens in the compiler service. The UI only orchestrates.
- **No DSL editing**: Step 7 is read-only by design (Resolved Decision #3).
- **No VLM provider in the UI**: Per Resolved Decision #6, the model is configured by deployment env vars, not by the user.
