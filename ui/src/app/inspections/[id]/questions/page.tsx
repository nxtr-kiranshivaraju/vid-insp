"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { compiler } from "@/lib/api-client/compiler";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { QuestionCard } from "@/components/wizard/question-card";
import { StaleBanner } from "@/components/wizard/wizard-shell";

export default function QuestionsPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { toast } = useToast();
  const key = `/sessions/${params.id}/questions`;
  const { data, error, isLoading, mutate } = useSWR(key, () => compiler.listQuestions(params.id));
  const [approving, setApproving] = useState(false);

  async function approve() {
    setApproving(true);
    try {
      const result = await compiler.approveQuestions(params.id);
      toast(`Generated rules for ${result.question_count} questions.`, "success");
      router.push(`/inspections/${params.id}/rules`);
    } catch (err) {
      toast(`Approval failed: ${(err as Error).message}`, "error");
    } finally {
      setApproving(false);
    }
  }

  if (isLoading) return <Spinner />;
  if (error) return <p className="text-sm text-destructive">Failed to load questions.</p>;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Step 3 · Review questions</h2>
        <p className="text-sm text-muted-foreground">
          One VLM prompt + output schema per intent. Confirm{" "}
          <span className="font-medium">violator_description</span> is present for multi-agent
          rules (ARCH-3).
        </p>
      </div>

      {data.downstream_stale && (
        <StaleBanner message="Re-approve to regenerate rules and DSL." />
      )}

      {data.questions.length === 0 ? (
        <p className="text-sm text-muted-foreground">No questions generated.</p>
      ) : (
        <div className="space-y-4">
          {data.questions.map((q) => (
            <QuestionCard
              key={q.idx}
              question={q}
              onSave={async (patch) => {
                await compiler.updateQuestion(params.id, q.idx, patch);
                await mutate();
                toast("Saved.", "success");
              }}
              onRegenerate={async (hint) => {
                await compiler.regenerateQuestion(params.id, q.idx, hint);
                await mutate();
                toast("Question regenerated.", "success");
              }}
            />
          ))}
        </div>
      )}

      <div className="flex justify-between border-t pt-4">
        <Button
          variant="outline"
          onClick={() => router.push(`/inspections/${params.id}/intents`)}
        >
          Back
        </Button>
        <Button onClick={approve} disabled={approving || data.questions.length === 0}>
          {approving ? "Generating rules…" : "Approve questions"}
        </Button>
      </div>
    </div>
  );
}
