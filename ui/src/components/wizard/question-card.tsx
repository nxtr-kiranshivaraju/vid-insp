"use client";

import { useState } from "react";
import type { Question } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

interface Props {
  question: Question;
  onSave(patch: Partial<Question>): Promise<void>;
  onRegenerate(hint?: string): Promise<void>;
}

export function QuestionCard({ question, onSave, onRegenerate }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Question>(question);
  const [busy, setBusy] = useState<"save" | "regen" | null>(null);
  const [hint, setHint] = useState("");

  const props = question.output_schema.properties;
  const hasViolator = "violator_description" in props;
  const hasConfidence = "confidence" in props;

  return (
    <Card data-testid={`question-${question.idx}`}>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="text-base">
            Question {question.idx + 1} · for intent #{question.intent_idx + 1}
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            target={question.target} · sample_every={question.sample_every}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={hasConfidence ? "success" : "destructive"}>
            {hasConfidence ? "confidence ✓" : "missing confidence"}
          </Badge>
          <Badge
            variant={hasViolator ? "success" : "outline"}
            data-testid={`violator-badge-${question.idx}`}
            title="ARCH-3: violator_description enables localization for multi-agent rules."
          >
            {hasViolator ? "violator_description ✓" : "no violator_description"}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div>
          <Label className="mb-1 block">VLM prompt</Label>
          {!editing ? (
            <pre className="whitespace-pre-wrap rounded-md bg-muted p-3 text-sm font-mono">
              {question.prompt}
            </pre>
          ) : (
            <Textarea
              rows={8}
              value={draft.prompt}
              onChange={(e) => setDraft({ ...draft, prompt: e.target.value })}
            />
          )}
        </div>

        <div>
          <Label className="mb-1 block">Output schema</Label>
          <ul className="divide-y rounded-md border text-sm">
            {Object.entries(props).map(([name, spec]) => {
              const required = question.output_schema.required.includes(name);
              return (
                <li key={name} className="flex items-center justify-between px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono">{name}</span>
                    <Badge variant="outline" className="text-[10px]">
                      {spec.type}
                    </Badge>
                    {required && (
                      <Badge variant="secondary" className="text-[10px]">
                        required
                      </Badge>
                    )}
                  </div>
                  {spec.description && (
                    <span className="text-xs text-muted-foreground">{spec.description}</span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-4">
          <Input
            placeholder="Optional regenerate hint"
            value={hint}
            onChange={(e) => setHint(e.target.value)}
            className="max-w-md"
          />
          <div className="flex gap-2">
            {!editing ? (
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                Edit prompt
              </Button>
            ) : (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setDraft(question);
                    setEditing(false);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  disabled={busy === "save"}
                  onClick={async () => {
                    setBusy("save");
                    try {
                      await onSave({ prompt: draft.prompt });
                      setEditing(false);
                    } finally {
                      setBusy(null);
                    }
                  }}
                >
                  {busy === "save" ? <Spinner /> : "Save"}
                </Button>
              </>
            )}
            <Button
              variant="outline"
              size="sm"
              disabled={busy !== null}
              onClick={async () => {
                setBusy("regen");
                try {
                  await onRegenerate(hint || undefined);
                  setHint("");
                } finally {
                  setBusy(null);
                }
              }}
            >
              {busy === "regen" ? <Spinner /> : "Regenerate"}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
