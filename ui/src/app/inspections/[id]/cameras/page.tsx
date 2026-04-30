"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { compiler } from "@/lib/api-client/compiler";
import { runtime } from "@/lib/api-client/runtime";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";

export default function CamerasPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { toast } = useToast();
  const key = `/sessions/${params.id}/cameras`;
  const { data, error, isLoading, mutate } = useSWR(key, () => compiler.listCameras(params.id));

  const [name, setName] = useState("");
  const [rtsp, setRtsp] = useState("");
  const [tz, setTz] = useState("UTC");
  const [adding, setAdding] = useState(false);
  const [probing, setProbing] = useState(false);
  const [probeResult, setProbeResult] = useState<{ ok: boolean; message: string } | null>(null);

  async function addCamera(e: React.FormEvent) {
    e.preventDefault();
    setAdding(true);
    try {
      await compiler.addCamera(params.id, { name, rtsp_url: rtsp, timezone: tz });
      await mutate();
      setName("");
      setRtsp("");
      setProbeResult(null);
      toast("Camera added.", "success");
    } catch (err) {
      toast(`Failed: ${(err as Error).message}`, "error");
    } finally {
      setAdding(false);
    }
  }

  async function probe() {
    if (!rtsp) return;
    setProbing(true);
    setProbeResult(null);
    try {
      const result = await runtime.probe(rtsp);
      setProbeResult({ ok: result.ok, message: result.message });
    } catch (err) {
      setProbeResult({ ok: false, message: (err as Error).message });
    } finally {
      setProbing(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Step 5 · Cameras</h2>
        <p className="text-sm text-muted-foreground">
          RTSP URLs are stored as secret references (ARCH-4); only a masked preview is shown after
          save.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Add camera</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid grid-cols-2 gap-4" onSubmit={addCamera}>
            <div className="space-y-2">
              <Label htmlFor="cam-name">Friendly name</Label>
              <Input
                id="cam-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Loading bay"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cam-tz">Timezone</Label>
              <Input
                id="cam-tz"
                value={tz}
                onChange={(e) => setTz(e.target.value)}
                placeholder="America/New_York"
                required
              />
            </div>
            <div className="col-span-2 space-y-2">
              <Label htmlFor="cam-rtsp">RTSP URL</Label>
              <div className="flex gap-2">
                <Input
                  id="cam-rtsp"
                  type="password"
                  value={rtsp}
                  onChange={(e) => setRtsp(e.target.value)}
                  placeholder="rtsp://user:pass@host:554/stream"
                  required
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={probe}
                  disabled={probing || !rtsp}
                >
                  {probing ? <Spinner /> : "Test connectivity"}
                </Button>
              </div>
              {probeResult && (
                <p
                  className={
                    probeResult.ok
                      ? "text-sm text-green-700"
                      : "text-sm text-destructive"
                  }
                  data-testid="probe-result"
                >
                  {probeResult.ok ? "✓ " : "✗ "}
                  {probeResult.message}
                </p>
              )}
            </div>
            <div className="col-span-2 flex justify-end">
              <Button type="submit" disabled={adding || !name || !rtsp}>
                {adding ? "Adding…" : "Add camera"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Configured cameras</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <Spinner />}
          {error && <p className="text-sm text-destructive">Failed to load cameras.</p>}
          {data && data.cameras.length === 0 && (
            <p className="text-sm text-muted-foreground">No cameras yet.</p>
          )}
          {data && data.cameras.length > 0 && (
            <ul className="divide-y">
              {data.cameras.map((cam) => (
                <li key={cam.id} className="flex items-center justify-between py-3">
                  <div className="space-y-1">
                    <p className="font-medium">{cam.name}</p>
                    <p className="font-mono text-xs text-muted-foreground">
                      {cam.rtsp_url_masked} · tz={cam.timezone}
                    </p>
                    <Badge variant="outline" className="text-[10px]">
                      secret_ref={cam.rtsp_secret_ref}
                    </Badge>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={async () => {
                      await compiler.deleteCamera(params.id, cam.id);
                      await mutate();
                      toast("Camera removed.", "success");
                    }}
                  >
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between border-t pt-4">
        <Button
          variant="outline"
          onClick={() => router.push(`/inspections/${params.id}/rules`)}
        >
          Back
        </Button>
        <Button
          onClick={() => router.push(`/inspections/${params.id}/channels`)}
          disabled={!data || data.cameras.length === 0}
        >
          Next: Channels
        </Button>
      </div>
    </div>
  );
}
