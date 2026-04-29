"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { compiler } from "@/lib/api-client/compiler";
import { runtime } from "@/lib/api-client/runtime";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import type { CommitResult } from "@/lib/types";

type Gate = { name: string; status: "pass" | "fail" | "warn"; detail: string };

export default function DeployPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { toast } = useToast();
  const [committing, setCommitting] = useState(false);
  const [committed, setCommitted] = useState<CommitResult | null>(null);
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const [preflight, setPreflight] = useState<Gate[] | null>(null);
  const [preflighting, setPreflighting] = useState(false);
  const [going, setGoing] = useState(false);

  async function commit() {
    setCommitting(true);
    try {
      const result = await compiler.commit(params.id);
      setCommitted(result);
      const dep = await runtime.createDeployment({ registry_ref: result.registry_ref });
      setDeploymentId(dep.deployment_id);
      toast("DSL committed and deployment created.", "success");
    } catch (err) {
      toast(`Commit failed: ${(err as Error).message}`, "error");
    } finally {
      setCommitting(false);
    }
  }

  async function runPreflight() {
    if (!deploymentId) return;
    setPreflighting(true);
    try {
      const result = await runtime.preflight(deploymentId);
      setPreflight(result.gates);
    } catch (err) {
      toast(`Preflight failed: ${(err as Error).message}`, "error");
    } finally {
      setPreflighting(false);
    }
  }

  async function goLive() {
    if (!deploymentId) return;
    setGoing(true);
    try {
      await runtime.goLive(deploymentId);
      toast("Deployment is live.", "success");
      router.push(`/monitor/${deploymentId}`);
    } catch (err) {
      toast(`Go-live failed: ${(err as Error).message}`, "error");
    } finally {
      setGoing(false);
    }
  }

  // `warn` is non-blocking by design — only an explicit `fail` gates Go Live.
  const canGoLive = preflight ? preflight.every((g) => g.status !== "fail") : false;
  const hasFail = !!preflight?.some((g) => g.status === "fail");

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Step 8 · Deploy</h2>
        <p className="text-sm text-muted-foreground">
          Commit the DSL to the registry, run preflight (G3–G7), and go live.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>1. Commit DSL</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {committed ? (
            <div className="space-y-1 text-sm">
              <p>
                <span className="text-muted-foreground">Customer:</span>{" "}
                <span className="font-mono">{committed.registry_ref.customer}</span>
              </p>
              <p>
                <span className="text-muted-foreground">Inspection:</span>{" "}
                <span className="font-mono">{committed.registry_ref.inspection_id}</span>
              </p>
              <p>
                <span className="text-muted-foreground">Version:</span>{" "}
                <span className="font-mono">v{committed.registry_ref.version}</span>
              </p>
              <p>
                <span className="text-muted-foreground">SHA:</span>{" "}
                <span className="font-mono">{committed.registry_ref.sha256.slice(0, 16)}…</span>
              </p>
            </div>
          ) : (
            <Button onClick={commit} disabled={committing}>
              {committing ? "Committing…" : "Commit and create deployment"}
            </Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. Preflight (G3–G7)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {!deploymentId ? (
            <p className="text-sm text-muted-foreground">Commit first to enable preflight.</p>
          ) : !preflight ? (
            <Button onClick={runPreflight} disabled={preflighting}>
              {preflighting ? "Running…" : "Run preflight"}
            </Button>
          ) : (
            <ul className="divide-y rounded-md border">
              {preflight.map((g) => (
                <li
                  key={g.name}
                  className="flex items-center justify-between px-3 py-2 text-sm"
                  data-testid={`gate-${g.name}`}
                >
                  <div>
                    <span className="font-mono">{g.name}</span>
                    <p className="text-xs text-muted-foreground">{g.detail}</p>
                  </div>
                  <Badge
                    variant={
                      g.status === "pass"
                        ? "success"
                        : g.status === "warn"
                          ? "warning"
                          : "destructive"
                    }
                  >
                    {g.status}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3. Go live</CardTitle>
        </CardHeader>
        <CardContent>
          <Button
            onClick={goLive}
            disabled={!canGoLive || going}
            data-testid="go-live"
          >
            {going ? <Spinner /> : "Go live"}
          </Button>
          {hasFail && (
            <p className="mt-2 text-xs text-muted-foreground">
              All failing gates must be resolved before going live. Warnings are non-blocking.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between border-t pt-4">
        <Button
          variant="outline"
          onClick={() => router.push(`/inspections/${params.id}/preview`)}
        >
          Back
        </Button>
      </div>
    </div>
  );
}
