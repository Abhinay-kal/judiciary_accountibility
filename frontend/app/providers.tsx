"use client";

import { ReactNode } from "react";

// Initialize safe storage on client mount
if (typeof window !== 'undefined') {
  import('@/lib/storage').catch(() => {});
}

export function Providers({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
