import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { HealthSummary } from "@/lib/types";
import { cn, formatTimestamp } from "@/lib/utils";

export function CameraGrid({ health }: { health: HealthSummary }) {
  const cameras = Object.entries(health.cameras);
  if (cameras.length === 0) {
    return <p className="text-sm text-muted-foreground">No cameras in this deployment.</p>;
  }
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
      {cameras.map(([id, cam]) => (
        <Card
          key={id}
          data-testid={`camera-${id}`}
          className={cn(
            "border",
            (cam.status === "failed" || cam.status === "backoff") && "border-destructive border-2",
          )}
        >
          <CardContent className="space-y-2 py-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium">{id}</p>
                <p className="text-xs text-muted-foreground">
                  Last frame: {cam.last_frame ? formatTimestamp(cam.last_frame) : "—"}
                </p>
              </div>
              <Badge
                variant={
                  cam.status === "ok"
                    ? "success"
                    : cam.status === "backoff"
                      ? "warning"
                      : "destructive"
                }
              >
                {cam.status}
              </Badge>
            </div>
            <div className="aspect-video w-full overflow-hidden rounded-md bg-muted">
              {cam.thumbnail_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={cam.thumbnail_url}
                  alt={`${id} thumbnail`}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                  no frame
                </div>
              )}
            </div>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
              <dt className="text-muted-foreground">Observations</dt>
              <dd>{cam.observation_count ?? 0}</dd>
              <dt className="text-muted-foreground">Retries</dt>
              <dd>{cam.retry_count}</dd>
              <dt className="text-muted-foreground">Last alert</dt>
              <dd>{cam.last_alert_at ? formatTimestamp(cam.last_alert_at) : "—"}</dd>
            </dl>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
