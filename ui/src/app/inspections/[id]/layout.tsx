import { WizardShell } from "@/components/wizard/wizard-shell";

export default function InspectionLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { id: string };
}) {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase text-muted-foreground">Session {params.id}</p>
        <h1 className="text-2xl font-semibold">Authoring wizard</h1>
      </div>
      <WizardShell sessionId={params.id}>{children}</WizardShell>
    </div>
  );
}
