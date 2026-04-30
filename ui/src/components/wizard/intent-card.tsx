"use client";

import { useState } from "react";
import type { Intent, Severity, CheckType } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";

const CHECK_TYPES: CheckType[] = [
  "presence_required",
  "presence_forbidden",
  "count_threshold",
  "behavior",
  "interaction",
  "state",
];

const SEVERITIES: Severity[] = ["low", "medium", "high", "critical"];

interface Props {
  intent: Intent;
  onSave(patch: Partial<Intent>): Promise<void>;
  onRegenerate(hint?: string): Promise<void>;
  onDelete(): Promise<void>;
}

export function IntentCard({ intent, onSave, onRegenerate, onDelete }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Intent>(intent);
  const [busy, setBusy] = useState<"save" | "regen" | "delete" | null>(null);
  const [hint, setHint] = useState("");

  async function handleSave() {
    setBusy("save");
    try {
      await onSave({
        check_type: draft.check_type,
        entity: draft.entity,
        location: draft.location,
        required: draft.required,
        schedule: draft.schedule,
        severity: draft.severity,
      });
      setEditing(false);
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card data-testid={`intent-${intent.idx}`}>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div className="space-y-1">
          <CardTitle className="text-base">
            Intent {intent.idx + 1}: {intent.entity}
          </CardTitle>
          <p className="text-xs text-muted-foreground">{intent.original_text}</p>
        </div>
        <Badge variant={severityVariant(intent.severity)}>{intent.severity}</Badge>
      </CardHeader>

      <CardContent className="space-y-4">
        {!editing ? (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <Field label="Check type" value={intent.check_type} />
            <Field label="Entity" value={intent.entity} />
            <Field label="Location" value={intent.location ?? "—"} />
            <Field label="Required" value={intent.required ? "yes" : "no"} />
            <Field label="Schedule" value={intent.schedule ?? "always"} />
            <Field label="Severity" value={intent.severity} />
          </dl>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor={`ct-${intent.idx}`}>Check type</Label>
              <Select
                id={`ct-${intent.idx}`}
                value={draft.check_type}
                onChange={(e) =>
                  setDraft({ ...draft, check_type: e.target.value as CheckType })
                }
              >
                {CHECK_TYPES.map((ct) => (
                  <option key={ct} value={ct}>
                    {ct}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor={`sev-${intent.idx}`}>Severity</Label>
              <Select
                id={`sev-${intent.idx}`}
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
            <div className="space-y-2">
              <Label htmlFor={`ent-${intent.idx}`}>Entity</Label>
              <Input
                id={`ent-${intent.idx}`}
                value={draft.entity}
                onChange={(e) => setDraft({ ...draft, entity: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`loc-${intent.idx}`}>Location</Label>
              <Input
                id={`loc-${intent.idx}`}
                value={draft.location ?? ""}
                onChange={(e) => setDraft({ ...draft, location: e.target.value || null })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`sch-${intent.idx}`}>Schedule</Label>
              <Input
                id={`sch-${intent.idx}`}
                value={draft.schedule ?? ""}
                onChange={(e) => setDraft({ ...draft, schedule: e.target.value || null })}
                placeholder="always"
              />
            </div>
            <div className="flex items-center gap-2 pt-7">
              <input
                id={`req-${intent.idx}`}
                type="checkbox"
                checked={draft.required}
                onChange={(e) => setDraft({ ...draft, required: e.target.checked })}
              />
              <Label htmlFor={`req-${intent.idx}`}>Required</Label>
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-4">
          <div className="flex flex-1 items-center gap-2">
            <Input
              placeholder="Optional hint for regenerate (e.g. also check safety boots)"
              value={hint}
              onChange={(e) => setHint(e.target.value)}
              className="max-w-md"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {!editing ? (
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                Edit
              </Button>
            ) : (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setDraft(intent);
                    setEditing(false);
                  }}
                  disabled={busy === "save"}
                >
                  Cancel
                </Button>
                <Button size="sm" onClick={handleSave} disabled={busy === "save"}>
                  {busy === "save" ? <Spinner /> : "Save"}
                </Button>
              </>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                setBusy("regen");
                try {
                  await onRegenerate(hint || undefined);
                  setHint("");
                } finally {
                  setBusy(null);
                }
              }}
              disabled={busy !== null}
            >
              {busy === "regen" ? <Spinner /> : "Regenerate"}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={async () => {
                setBusy("delete");
                try {
                  await onDelete();
                } finally {
                  setBusy(null);
                }
              }}
              disabled={busy !== null}
            >
              Delete
            </Button>
          </div>
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
