"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { compiler } from "@/lib/api-client/compiler";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { RuleCard } from "@/components/wizard/rule-card";

export default function RulesPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { toast } = useToast();
  const key = `/sessions/${params.id}/rules`;
  const { data, error, isLoading, mutate } = useSWR(key, () => compiler.listRules(params.id));
  const [approving, setApproving] = useState(false);

  async function approve() {
    setApproving(true);
    try {
      await compiler.approveRules(params.id);
      toast("Rules approved.", "success");
      router.push(`/inspections/${params.id}/cameras`);
    } catch (err) {
      toast(`Approval failed: ${(err as Error).message}`, "error");
    } finally {
      setApproving(false);
    }
  }

  if (isLoading) return <Spinner />;
  if (error) return <p className="text-sm text-destructive">Failed to load rules.</p>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Step 4 · Review rules</h2>
        <p className="text-sm text-muted-foreground">
          Adjust voting thresholds and cooldowns. Hover{" "}
          <span className="font-medium">Sustained threshold</span> for an explanation.
        </p>
      </div>

      {data.rules.length === 0 ? (
        <p className="text-sm text-muted-foreground">No rules generated.</p>
      ) : (
        <div className="space-y-4">
          {data.rules.map((rule) => (
            <RuleCard
              key={rule.idx}
              rule={rule}
              onSave={async (patch) => {
                await compiler.updateRule(params.id, rule.idx, patch);
                await mutate();
                toast("Rule saved.", "success");
              }}
            />
          ))}
        </div>
      )}

      <div className="flex justify-between border-t pt-4">
        <Button
          variant="outline"
          onClick={() => router.push(`/inspections/${params.id}/questions`)}
        >
          Back
        </Button>
        <Button onClick={approve} disabled={approving || data.rules.length === 0}>
          {approving ? "Approving…" : "Approve rules"}
        </Button>
      </div>
    </div>
  );
}
