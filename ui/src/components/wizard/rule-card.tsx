"use client";

import { useState } from "react";
import type { Rule, Severity } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip } from "@/components/ui/tooltip";

const SEVERITIES: Severity[] = ["low", "medium", "high", "critical"];

interface Props {
  rule: Rule;
  onSave(patch: Partial<Rule>): Promise<void>;
}

export function RuleCard({ rule, onSave }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Rule>(rule);
  const [busy, setBusy] = useState(false);

  return (
    <Card data-testid={`rule-${rule.idx}`}>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <CardTitle className="text-base">{rule.rule_id}</CardTitle>
        <Badge variant={severityVariant(rule.severity)}>{rule.severity}</Badge>
      </CardHeader>

      <CardContent className="space-y-4">
        <div>
          <Label className="mb-1 block">Expression</Label>
          <pre className="whitespace-pre-wrap rounded-md bg-muted p-3 text-sm font-mono">
            {rule.expression}
          </pre>
        </div>

        {!editing ? (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <Field label="Sustained for" value={rule.sustained_for} />
            <FieldWithTooltip
              label="Sustained threshold"
              value={String(rule.sustained_threshold)}
              tooltip="ARCH-1: Number of qualifying observations within the window required to fire. The runtime votes across observations to suppress flicker."
            />
            <Field label="Cooldown" value={rule.cooldown} />
            <Field label="Severity" value={rule.severity} />
          </dl>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor={`sf-${rule.idx}`}>Sustained for</Label>
              <Input
                id={`sf-${rule.idx}`}
                value={draft.sustained_for}
                onChange={(e) => setDraft({ ...draft, sustained_for: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`st-${rule.idx}`}>Sustained threshold</Label>
              <Input
                id={`st-${rule.idx}`}
                type="number"
                min={1}
                value={draft.sustained_threshold}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    sustained_threshold: Number(e.target.value) || 1,
                  })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`cd-${rule.idx}`}>Cooldown</Label>
              <Input
                id={`cd-${rule.idx}`}
                value={draft.cooldown}
                onChange={(e) => setDraft({ ...draft, cooldown: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`sev-${rule.idx}`}>Severity</Label>
              <Select
                id={`sev-${rule.idx}`}
                value={draft.severity}
                onChange={(e) => setDraft({ ...draft, severity: e.target.value as Severity })}
              >
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </Select>
            </div>
          </div>
        )}

        <div className="flex justify-end gap-2 border-t pt-4">
          {!editing ? (
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              Edit thresholds
            </Button>
          ) : (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setDraft(rule);
                  setEditing(false);
                }}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await onSave({
                      sustained_for: draft.sustained_for,
                      sustained_threshold: draft.sustained_threshold,
                      cooldown: draft.cooldown,
                      severity: draft.severity,
                    });
                    setEditing(false);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {busy ? <Spinner /> : "Save"}
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-mono">{value}</dd>
    </>
  );
}

function FieldWithTooltip({
  label,
  value,
  tooltip,
}: {
  label: string;
  value: string;
  tooltip: string;
}) {
  return (
    <>
      <dt className="text-muted-foreground">
        <Tooltip content={tooltip}>
          <span className="cursor-help underline decoration-dotted">{label}</span>
        </Tooltip>
      </dt>
      <dd className="font-mono">{value}</dd>
    </>
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
