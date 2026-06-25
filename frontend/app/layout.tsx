import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Court Case Delay & Justice Tracker - India",
  description: "Public accountability platform for judicial delay metrics"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-body">
        <Providers>
          <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
            <header className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-ink/10 bg-white/65 px-4 py-3 backdrop-blur">
              <Link href="/hub" className="font-display text-lg text-ink">
                Unified Hub
              </Link>
              <nav className="flex flex-wrap gap-2 text-xs">
                <Link href="/hub" className="rounded-lg border border-ink/15 px-2 py-1 hover:bg-white/80">Home</Link>
                <Link href="/legacy" className="rounded-lg border border-ink/15 px-2 py-1 hover:bg-white/80">Legacy</Link>
                <Link href="/search" className="rounded-lg border border-ink/15 px-2 py-1 hover:bg-white/80">Search</Link>
                <Link href="/open-data" className="rounded-lg border border-ink/15 px-2 py-1 hover:bg-white/80">Open Data</Link>
                <Link href="/admin/population" className="rounded-lg border border-ink/15 px-2 py-1 hover:bg-white/80">Admin</Link>
              </nav>
            </header>
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
