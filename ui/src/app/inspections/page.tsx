"use client";

import Link from "next/link";
import useSWR from "swr";
import { compiler } from "@/lib/api-client/compiler";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { formatTimestamp } from "@/lib/utils";

export default function InspectionsPage() {
  const { data, error, isLoading } = useSWR("/sessions", () => compiler.listSessions());

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Inspections</h1>
          <p className="text-sm text-muted-foreground">Author and review inspection rules.</p>
        </div>
        <Link href="/inspections/new">
          <Button>New inspection</Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Sessions</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <Spinner />}
          {error && <p className="text-sm text-destructive">Failed to load sessions.</p>}
          {data && data.sessions.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No inspections yet. Click <span className="font-medium">New inspection</span> to start.
            </p>
          )}
          {data && data.sessions.length > 0 && (
            <ul className="divide-y">
              {data.sessions.map((s) => (
                <li key={s.session_id} className="flex items-center justify-between py-3">
                  <div className="space-y-1">
                    <Link
                      href={`/inspections/${s.session_id}/intents`}
                      className="font-medium hover:underline"
                    >
                      {s.title || s.session_id}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      Updated {formatTimestamp(s.updated_at)}
                    </p>
                  </div>
                  <Badge variant="outline">{s.status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
