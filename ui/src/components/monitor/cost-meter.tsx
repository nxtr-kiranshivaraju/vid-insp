import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { CostSummary } from "@/lib/types";

export function CostMeter({ cost }: { cost: CostSummary }) {
  const cameras = Object.entries(cost.by_camera);
  const max = Math.max(...cameras.map(([, v]) => v), 0.01);
  const overBudget =
    cost.budget_threshold_usd != null && cost.rolling_hour_usd >= cost.budget_threshold_usd;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Cost</CardTitle>
        {overBudget && <Badge variant="destructive">over budget</Badge>}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Stat label="$/hour" value={`$${cost.rolling_hour_usd.toFixed(2)}`} />
          <Stat label="$/day" value={`$${cost.rolling_day_usd.toFixed(2)}`} />
        </div>
        {cost.budget_threshold_usd != null && (
          <p className="text-xs text-muted-foreground">
            Budget threshold: ${cost.budget_threshold_usd.toFixed(2)}/hour
          </p>
        )}
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Per camera (rolling hour)</p>
          {cameras.length === 0 ? (
            <p className="text-sm text-muted-foreground">No data.</p>
          ) : (
            <ul className="space-y-1">
              {cameras.map(([cam, value]) => (
                <li key={cam} className="space-y-0.5 text-xs">
                  <div className="flex justify-between">
                    <span className="font-mono">{cam}</span>
                    <span>${value.toFixed(3)}</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-muted">
                    <div
                      className={cn(
                        "h-1.5 rounded-full",
                        overBudget ? "bg-destructive" : "bg-primary",
                      )}
                      style={{ width: `${Math.min(100, (value / max) * 100)}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-mono text-lg">{value}</p>
    </div>
  );
}
