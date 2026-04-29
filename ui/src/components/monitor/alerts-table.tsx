"use client";

import { useMemo, useState } from "react";
import type { Alert, Severity } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { formatTimestamp } from "@/lib/utils";

type SortKey = "timestamp" | "severity" | "camera";

const SEV_RANK: Record<Severity, number> = { critical: 4, high: 3, medium: 2, low: 1 };

export function AlertsTable({ alerts }: { alerts: Alert[] }) {
  const [severity, setSeverity] = useState<"all" | Severity>("all");
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");

  const filtered = useMemo(() => {
    const f = severity === "all" ? alerts : alerts.filter((a) => a.severity === severity);
    return [...f].sort((a, b) => {
      switch (sortKey) {
        case "severity":
          return SEV_RANK[b.severity] - SEV_RANK[a.severity];
        case "camera":
          return a.camera_id.localeCompare(b.camera_id);
        case "timestamp":
        default:
          return b.timestamp.localeCompare(a.timestamp);
      }
    });
  }, [alerts, severity, sortKey]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="space-y-1 text-xs">
          <span className="text-muted-foreground">Severity</span>
          <Select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as "all" | Severity)}
          >
            <option value="all">all</option>
            <option value="critical">critical</option>
            <option value="high">high</option>
            <option value="medium">medium</option>
            <option value="low">low</option>
          </Select>
        </label>
        <label className="space-y-1 text-xs">
          <span className="text-muted-foreground">Sort by</span>
          <Select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
            <option value="timestamp">timestamp (newest)</option>
            <option value="severity">severity</option>
            <option value="camera">camera</option>
          </Select>
        </label>
      </div>
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs uppercase">
            <tr>
              <th className="px-3 py-2 text-left">Time</th>
              <th className="px-3 py-2 text-left">Camera</th>
              <th className="px-3 py-2 text-left">Rule</th>
              <th className="px-3 py-2 text-left">Severity</th>
              <th className="px-3 py-2 text-left">Message</th>
              <th className="px-3 py-2 text-left">Violator</th>
              <th className="px-3 py-2 text-left">Snapshot</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-muted-foreground">
                  No alerts.
                </td>
              </tr>
            ) : (
              filtered.map((a) => (
                <tr key={a.id} className="border-t" data-testid={`alert-${a.id}`}>
                  <td className="px-3 py-2 font-mono text-xs">{formatTimestamp(a.timestamp)}</td>
                  <td className="px-3 py-2 font-mono text-xs">{a.camera_id}</td>
                  <td className="px-3 py-2 font-mono text-xs">{a.rule_id}</td>
                  <td className="px-3 py-2">
                    <Badge variant={severityVariant(a.severity)}>{a.severity}</Badge>
                  </td>
                  <td className="px-3 py-2">{a.message}</td>
                  <td className="px-3 py-2 text-xs italic text-muted-foreground">
                    {a.violator_description ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    {a.snapshot_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={a.snapshot_url}
                        alt={`Snapshot for ${a.id}`}
                        className="h-12 w-20 rounded object-cover"
                      />
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function severityVariant(s: Severity) {
  switch (s) {
    case "critical":
    case "high":
      return "destructive" as const;
    case "medium":
      return "warning" as const;
    default:
      return "secondary" as const;
  }
}
