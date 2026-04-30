"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { compiler } from "@/lib/api-client/compiler";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";

export default function NewInspectionPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const paragraphs = text
        .split(/\n\s*\n/)
        .map((p) => p.trim())
        .filter(Boolean);
      if (paragraphs.length === 0) {
        toast("Please describe at least one inspection rule.", "error");
        return;
      }
      const { session_id } = await compiler.createSession(paragraphs);
      toast("Intents extracted. Review them next.", "success");
      router.push(`/inspections/${session_id}/intents`);
    } catch (err) {
      toast(`Failed to create session: ${(err as Error).message}`, "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">New inspection</h1>
        <p className="text-sm text-muted-foreground">
          Step 1 of 8 · Describe the rules in plain English.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>What should the system check?</CardTitle>
          <CardDescription>
            Paste one or more paragraphs. Separate distinct rules with a blank line. The compiler
            will extract intents from this text.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <Textarea
              rows={12}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Workers in the loading bay must wear hard hats and hi-vis vests at all times. Forklifts must not operate within 3 metres of a person on foot."
            />
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push("/inspections")}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={submitting || !text.trim()}>
                {submitting ? "Extracting intents…" : "Extract intents"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
