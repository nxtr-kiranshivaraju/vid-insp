import type { Metadata } from "next";
import "./globals.css";
import { ToastProvider } from "@/components/ui/toast";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Video Inspection Console",
  description: "Author and monitor inspection rules in plain English.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background">
        <ToastProvider>
          <Header />
          <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
        </ToastProvider>
      </body>
    </html>
  );
}

function Header() {
  return (
    <header className="border-b">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/inspections" className="text-lg font-semibold">
          Video Inspection
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/inspections" className="hover:underline">
            Inspections
          </Link>
          <Link href="/monitor" className="hover:underline">
            Monitor
          </Link>
          <form action="/api/auth/logout" method="post">
            <button className="text-muted-foreground hover:underline" type="submit">
              Sign out
            </button>
          </form>
        </nav>
      </div>
    </header>
  );
}
