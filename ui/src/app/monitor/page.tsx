import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function MonitorIndex() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Monitor</h1>
        <p className="text-sm text-muted-foreground">
          Open the monitor for an active deployment.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>How to get here</CardTitle>
          <CardDescription>
            Deploy an inspection from the wizard to land on its monitor automatically. Otherwise,
            navigate to <span className="font-mono">/monitor/&lt;deployment_id&gt;</span>.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link href="/inspections" className="text-primary hover:underline">
            ← Back to inspections
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
