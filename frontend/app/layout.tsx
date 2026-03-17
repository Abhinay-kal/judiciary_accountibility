import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Court Case Delay & Justice Tracker - India",
  description: "Public accountability platform for judicial delay metrics"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-body">
        <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">{children}</main>
      </body>
    </html>
  );
}
