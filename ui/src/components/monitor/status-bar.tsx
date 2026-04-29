import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { RuntimeStatus } from "@/lib/types";
import { formatUptime } from "@/lib/utils";

const STATE_COLORS: Record<RuntimeStatus["state"], "success" | "warning" | "destructive" | "secondary"> = {
  running: "success",
  preflight: "warning",
  paused: "secondary",
  error: "destructive",
};

export function StatusBar({ status }: { status: RuntimeStatus }) {
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center gap-6 py-4">
        <div className="space-y-0.5">
          <p className="text-xs text-muted-foreground">State</p>
          <Badge variant={STATE_COLORS[status.state]} data-testid="status-state">
            {status.state}
          </Badge>
        </div>
        <Stat label="Uptime" value={formatUptime(status.uptime_seconds)} />
        <Stat label="DSL version" value={`v${status.dsl_version}`} />
        <Stat
          label="Cameras"
          value={`${status.cameras_active} active · ${status.cameras_failed} failed`}
        />
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-mono text-sm">{value}</p>
    </div>
  );
}
