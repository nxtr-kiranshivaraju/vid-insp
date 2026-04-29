import { server } from "./msw-server";
import { afterAll, afterEach, beforeAll } from "vitest";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
