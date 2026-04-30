"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { compiler } from "@/lib/api-client/compiler";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { IntentCard } from "@/components/wizard/intent-card";
import { StaleBanner } from "@/components/wizard/wizard-shell";

export default function IntentsPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { toast } = useToast();
  const key = `/sessions/${params.id}/intents`;
  const { data, error, isLoading, mutate } = useSWR(key, () => compiler.listIntents(params.id));
  const [approving, setApproving] = useState(false);

  async function approve() {
    setApproving(true);
    try {
      const result = await compiler.approveIntents(params.id);
      toast(`Generated ${result.intent_count} questions.`, "success");
      router.push(`/inspections/${params.id}/questions`);
    } catch (err) {
      toast(`Approval failed: ${(err as Error).message}`, "error");
    } finally {
      setApproving(false);
    }
  }

  if (isLoading) return <Spinner />;
  if (error) return <p className="text-sm text-destructive">Failed to load intents.</p>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Step 2 · Review intents</h2>
        <p className="text-sm text-muted-foreground">
          One card per extracted intent. Edit fields, regenerate, or delete. Approving runs Stage C
          to generate VLM prompts.
        </p>
      </div>

      {data.downstream_stale && (
        <StaleBanner message="Re-approve to regenerate questions, rules, and DSL." />
      )}

      {data.intents.length === 0 ? (
        <p className="text-sm text-muted-foreground">No intents extracted.</p>
      ) : (
        <div className="space-y-4">
          {data.intents.map((intent) => (
            <IntentCard
              key={intent.idx}
              intent={intent}
              onSave={async (patch) => {
                await compiler.updateIntent(params.id, intent.idx, patch);
                await mutate();
                toast("Saved.", "success");
              }}
              onRegenerate={async (hint) => {
                await compiler.regenerateIntent(params.id, intent.idx, hint);
                await mutate();
                toast("Intent regenerated.", "success");
              }}
              onDelete={async () => {
                await compiler.deleteIntent(params.id, intent.idx);
                await mutate();
                toast("Intent deleted.", "success");
              }}
            />
          ))}
        </div>
      )}

      <div className="flex justify-between border-t pt-4">
        <Button variant="outline" onClick={() => router.push("/inspections")}>
          Back
        </Button>
        <Button onClick={approve} disabled={approving || data.intents.length === 0}>
          {approving ? "Generating questions…" : "Approve intents"}
        </Button>
      </div>
    </div>
  );
}
