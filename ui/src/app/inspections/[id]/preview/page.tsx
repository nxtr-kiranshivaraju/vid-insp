"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { compiler } from "@/lib/api-client/compiler";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import type { ValidationResult } from "@/lib/types";

export default function PreviewPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { toast } = useToast();
  const [yaml, setYaml] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [doc, val] = await Promise.all([
          compiler.getDsl(params.id),
          compiler.validate(params.id),
        ]);
        if (cancelled) return;
        setYaml(doc);
        setValidation(val);
      } catch (err) {
        toast(`Failed: ${(err as Error).message}`, "error");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [params.id, toast]);

  async function revalidate() {
    setValidating(true);
    try {
      const val = await compiler.validate(params.id);
      setValidation(val);
      toast(val.valid ? "Validation passed." : "Validation failed.", val.valid ? "success" : "error");
    } catch (err) {
      toast(`Failed: ${(err as Error).message}`, "error");
    } finally {
      setValidating(false);
    }
  }

  function downloadYaml() {
    if (!yaml) return;
    const blob = new Blob([yaml], { type: "application/x-yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `inspection-${params.id}.yaml`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Step 7 · DSL preview</h2>
        <p className="text-sm text-muted-foreground">
          Read-only YAML. To edit, download, modify locally, and resubmit as a new paragraph.
        </p>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle>Validation</CardTitle>
          <Button variant="outline" size="sm" onClick={revalidate} disabled={validating}>
            {validating ? <Spinner /> : "Re-validate"}
          </Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {validation == null ? (
            <Spinner />
          ) : (
            <div className="flex flex-wrap gap-2">
              <Badge variant={validation.valid ? "success" : "destructive"}>
                Overall: {validation.valid ? "PASS" : "FAIL"}
              </Badge>
              <Badge
                variant={validation.g1_errors.length === 0 ? "success" : "destructive"}
                data-testid="g1-badge"
              >
                G1: {validation.g1_errors.length === 0 ? "pass" : `${validation.g1_errors.length} errors`}
              </Badge>
              <Badge
                variant={validation.g2_errors.length === 0 ? "success" : "destructive"}
                data-testid="g2-badge"
              >
                G2: {validation.g2_errors.length === 0 ? "pass" : `${validation.g2_errors.length} errors`}
              </Badge>
            </div>
          )}
          {validation && validation.g1_errors.length > 0 && (
            <ul className="list-disc pl-5 text-sm text-destructive">
              {validation.g1_errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
          {validation && validation.g2_errors.length > 0 && (
            <ul className="list-disc pl-5 text-sm text-destructive">
              {validation.g2_errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle>DSL document</CardTitle>
          <Button variant="outline" size="sm" onClick={downloadYaml} disabled={!yaml}>
            Download YAML
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Spinner />
          ) : (
            <pre
              data-testid="dsl-preview"
              className="max-h-[480px] overflow-auto rounded-md bg-muted p-4 text-xs font-mono"
            >
              {yaml}
            </pre>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between border-t pt-4">
        <Button
          variant="outline"
          onClick={() => router.push(`/inspections/${params.id}/channels`)}
        >
          Back
        </Button>
        <Button
          onClick={() => router.push(`/inspections/${params.id}/deploy`)}
          disabled={!validation?.valid}
        >
          Next: Deploy
        </Button>
      </div>
    </div>
  );
}
