import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { HealthSummary } from "@/lib/types";

export function HealthPanel({ health }: { health: HealthSummary }) {
  const coercion = Object.entries(health.vlm_coercion_errors);
  const gaps = Object.entries(health.observation_gaps);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Health</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <Section title="VLM schema-violation rate (ARCH-8)">
          {coercion.length === 0 ? (
            <p className="text-muted-foreground text-xs">No coercion errors.</p>
          ) : (
            <ul className="space-y-1 text-xs">
              {coercion.map(([qid, providers]) => (
                <li key={qid} className="space-y-0.5">
                  <span className="font-mono">{qid}</span>
                  <ul className="ml-4 list-disc">
                    {Object.entries(providers).map(([provider, n]) => (
                      <li key={provider}>
                        {provider}: <span className="font-mono">{n}</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Observation gaps (ARCH-7)">
          {gaps.length === 0 ? (
            <p className="text-muted-foreground text-xs">No gaps.</p>
          ) : (
            <ul className="space-y-1 text-xs">
              {gaps.map(([key, n]) => (
                <li key={key} className="flex justify-between font-mono">
                  <span>{key}</span>
                  <span>{n}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Camera retries (ARCH-6)">
          <ul className="space-y-1 text-xs">
            {Object.entries(health.cameras).map(([cam, h]) => (
              <li key={cam} className="flex justify-between font-mono">
                <span>{cam}</span>
                <span>retries={h.retry_count}</span>
              </li>
            ))}
          </ul>
        </Section>
      </CardContent>
    </Card>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <h3 className="text-xs font-semibold uppercase text-muted-foreground">{title}</h3>
      {children}
    </div>
  );
}
