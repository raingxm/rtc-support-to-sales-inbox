"use client";

import { AudioLines, Radio } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export function DeskFrame({ section, children }: { section: string; children: ReactNode }) {
  const pathname = usePathname();
  const onSupport = pathname === "/";
  const onCustomer = pathname.startsWith("/customer");

  return (
    <>
      <header className="topbar">
        <div className="frame topbar-content">
          <div className="brand">
            <span className="brand-icon"><AudioLines size={20} /></span>
            <strong>Relay Desk</strong>
            <span className="brand-divider" />
            <span className="brand-section">{section}</span>
          </div>
          <nav className="desk-nav" aria-label="Entries">
            <Link href="/" aria-current={onSupport ? "page" : undefined}>Support</Link>
            <Link href="/customer" aria-current={onCustomer ? "page" : undefined}>Customer</Link>
          </nav>
          <span className="demo"><Radio size={14} /> Demo workspace</span>
        </div>
      </header>
      {children}
    </>
  );
}
