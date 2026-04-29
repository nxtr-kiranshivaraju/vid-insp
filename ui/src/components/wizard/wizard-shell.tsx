"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";
import { cn } from "@/lib/utils";

const STEPS = [
  { slug: "intents", label: "Intents", index: 2 },
  { slug: "questions", label: "Questions", index: 3 },
  { slug: "rules", label: "Rules", index: 4 },
  { slug: "cameras", label: "Cameras", index: 5 },
  { slug: "channels", label: "Channels", index: 6 },
  { slug: "preview", label: "Preview", index: 7 },
  { slug: "deploy", label: "Deploy", index: 8 },
] as const;

export function WizardShell({
  sessionId,
  children,
}: {
  sessionId: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const activeSlug = pathname.split("/").pop();
  return (
    <div className="space-y-6">
      <nav aria-label="Wizard steps">
        <ol className="flex flex-wrap items-center gap-2 text-sm">
          {STEPS.map((s, i) => {
            const isActive = s.slug === activeSlug;
            return (
              <li key={s.slug} className="flex items-center gap-2">
                <Link
                  href={`/inspections/${sessionId}/${s.slug}`}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-3 py-1.5 transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                >
                  <span
                    className={cn(
                      "flex h-5 w-5 items-center justify-center rounded-full text-xs font-semibold",
                      isActive
                        ? "bg-primary-foreground text-primary"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    {s.index}
                  </span>
                  {s.label}
                </Link>
                {i < STEPS.length - 1 && <span className="text-muted-foreground">›</span>}
              </li>
            );
          })}
        </ol>
      </nav>
      <div>{children}</div>
    </div>
  );
}

export function StaleBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <span className="font-semibold">Downstream is stale:</span> {message}
    </div>
  );
}
