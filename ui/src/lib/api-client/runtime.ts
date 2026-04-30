import type {
  Alert,
  CostSummary,
  HealthSummary,
  ProbeResult,
  RuntimeStatus,
  Severity,
} from "@/lib/types";
import { request } from "./http";

const BASE = "/api/runtime";

export const runtime = {
  probe(rtsp_url: string): Promise<ProbeResult> {
    return request(`${BASE}/probe`, {
      method: "POST",
      body: JSON.stringify({ rtsp_url }),
    });
  },

  createDeployment(input: {
    registry_ref: { customer: string; inspection_id: string; version: number };
  }): Promise<{ deployment_id: string; state: string }> {
    return request(`${BASE}/deployments`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  preflight(deployment_id: string): Promise<{
    gates: { name: string; status: "pass" | "fail" | "warn"; detail: string }[];
  }> {
    return request(`${BASE}/deployments/${deployment_id}/preflight`, { method: "POST" });
  },

  goLive(deployment_id: string): Promise<{ state: string }> {
    return request(`${BASE}/deployments/${deployment_id}/go-live`, { method: "POST" });
  },

  status(deployment_id: string): Promise<RuntimeStatus> {
    return request(`${BASE}/deployments/${deployment_id}/status`);
  },

  alerts(
    deployment_id: string,
    opts: { limit?: number; severity?: Severity } = {},
  ): Promise<{ alerts: Alert[] }> {
    const qs = new URLSearchParams();
    if (opts.limit) qs.set("limit", String(opts.limit));
    if (opts.severity) qs.set("severity", opts.severity);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request(`${BASE}/deployments/${deployment_id}/alerts${suffix}`);
  },

  cost(deployment_id: string): Promise<CostSummary> {
    return request(`${BASE}/deployments/${deployment_id}/cost`);
  },

  health(deployment_id: string): Promise<HealthSummary> {
    return request(`${BASE}/deployments/${deployment_id}/health`);
  },
};
