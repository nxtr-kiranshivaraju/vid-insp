"use client";

import useSWR from "swr";
import { runtime } from "@/lib/api-client/runtime";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { StatusBar } from "@/components/monitor/status-bar";
import { CameraGrid } from "@/components/monitor/camera-grid";
import { AlertsTable } from "@/components/monitor/alerts-table";
import { CostMeter } from "@/components/monitor/cost-meter";
import { HealthPanel } from "@/components/monitor/health-panel";

const REFRESH = 5000;
// Disable focus/reconnect revalidation: with four hooks, tab focus would otherwise fire
// a 4-request burst on top of the 5s poll.
const SWR_OPTS = {
  refreshInterval: REFRESH,
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
};

export default function MonitorPage({ params }: { params: { deployment_id: string } }) {
  const id = params.deployment_id;
  const status = useSWR(["status", id], () => runtime.status(id), SWR_OPTS);
  const alerts = useSWR(["alerts", id], () => runtime.alerts(id, { limit: 50 }), SWR_OPTS);
  const cost = useSWR(["cost", id], () => runtime.cost(id), SWR_OPTS);
  const health = useSWR(["health", id], () => runtime.health(id), SWR_OPTS);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase text-muted-foreground">Deployment {id}</p>
        <h1 className="text-2xl font-semibold">Live monitor</h1>
        <p className="text-sm text-muted-foreground">Polls every 5 seconds.</p>
      </div>

      {status.data ? (
        <StatusBar status={status.data} />
      ) : status.isLoading ? (
        <Spinner />
      ) : (
        <p className="text-sm text-destructive">Failed to load status.</p>
      )}

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Cameras</CardTitle>
          </CardHeader>
          <CardContent>
            {health.data ? <CameraGrid health={health.data} /> : <Spinner />}
          </CardContent>
        </Card>
        <div className="space-y-6">
          {cost.data ? <CostMeter cost={cost.data} /> : <Spinner />}
          {health.data ? <HealthPanel health={health.data} /> : null}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent alerts</CardTitle>
        </CardHeader>
        <CardContent>
          {alerts.data ? <AlertsTable alerts={alerts.data.alerts} /> : <Spinner />}
        </CardContent>
      </Card>
    </div>
  );
}
