"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { compiler } from "@/lib/api-client/compiler";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import type { ChannelType } from "@/lib/types";

const CHANNEL_TYPES: { value: ChannelType; label: string; placeholder: string }[] = [
  { value: "slack", label: "Slack", placeholder: "https://hooks.slack.com/services/T.../B.../..." },
  { value: "pagerduty", label: "PagerDuty", placeholder: "https://events.pagerduty.com/..." },
  { value: "webhook", label: "Generic webhook", placeholder: "https://example.com/webhook" },
];

export default function ChannelsPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { toast } = useToast();
  const key = `/sessions/${params.id}/channels`;
  const { data, error, isLoading, mutate } = useSWR(key, () => compiler.listChannels(params.id));

  const [type, setType] = useState<ChannelType>("slack");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  const placeholder = CHANNEL_TYPES.find((t) => t.value === type)?.placeholder ?? "";

  async function addChannel(e: React.FormEvent) {
    e.preventDefault();
    setAdding(true);
    try {
      await compiler.addChannel(params.id, { type, name, url });
      await mutate();
      setName("");
      setUrl("");
      toast("Channel added.", "success");
    } catch (err) {
      toast(`Failed: ${(err as Error).message}`, "error");
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Step 6 · Alert channels</h2>
        <p className="text-sm text-muted-foreground">
          Webhook URLs are stored as secret references (ARCH-4); the URL is masked after save.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Add channel</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid grid-cols-2 gap-4" onSubmit={addChannel}>
            <div className="space-y-2">
              <Label htmlFor="ch-type">Type</Label>
              <Select
                id="ch-type"
                value={type}
                onChange={(e) => setType(e.target.value as ChannelType)}
              >
                {CHANNEL_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ch-name">Friendly name</Label>
              <Input
                id="ch-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="#safety-alerts"
                required
              />
            </div>
            <div className="col-span-2 space-y-2">
              <Label htmlFor="ch-url">Webhook URL</Label>
              <Input
                id="ch-url"
                type="password"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder={placeholder}
                required
              />
            </div>
            <div className="col-span-2 flex justify-end">
              <Button type="submit" disabled={adding || !name || !url}>
                {adding ? "Adding…" : "Add channel"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Configured channels</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <Spinner />}
          {error && <p className="text-sm text-destructive">Failed to load channels.</p>}
          {data && data.channels.length === 0 && (
            <p className="text-sm text-muted-foreground">No channels yet.</p>
          )}
          {data && data.channels.length > 0 && (
            <ul className="divide-y">
              {data.channels.map((c) => (
                <li key={c.id} className="flex items-center justify-between py-3">
                  <div className="space-y-1">
                    <p className="font-medium">
                      {c.name}{" "}
                      <Badge variant="outline" className="ml-1 text-[10px]">
                        {c.type}
                      </Badge>
                    </p>
                    <p className="font-mono text-xs text-muted-foreground">{c.url_masked}</p>
                    <Badge variant="outline" className="text-[10px]">
                      secret_ref={c.secret_ref}
                    </Badge>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={testingId === c.id}
                      onClick={async () => {
                        setTestingId(c.id);
                        try {
                          const result = await compiler.testChannel(params.id, c.id);
                          toast(
                            result.ok ? `Test sent: ${result.message}` : `Test failed: ${result.message}`,
                            result.ok ? "success" : "error",
                          );
                        } catch (err) {
                          toast(`Test failed: ${(err as Error).message}`, "error");
                        } finally {
                          setTestingId(null);
                        }
                      }}
                    >
                      {testingId === c.id ? <Spinner /> : "Test ping"}
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={async () => {
                        await compiler.deleteChannel(params.id, c.id);
                        await mutate();
                        toast("Channel removed.", "success");
                      }}
                    >
                      Remove
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between border-t pt-4">
        <Button
          variant="outline"
          onClick={() => router.push(`/inspections/${params.id}/cameras`)}
        >
          Back
        </Button>
        <Button
          onClick={() => router.push(`/inspections/${params.id}/preview`)}
          disabled={!data || data.channels.length === 0}
        >
          Next: Preview
        </Button>
      </div>
    </div>
  );
}
