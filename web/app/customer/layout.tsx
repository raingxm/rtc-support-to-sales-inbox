import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Your ticket | Relay Desk",
  description: "Open a ticket and add another message without an account.",
};

export default function CustomerLayout({ children }: { children: ReactNode }) {
  return children;
}
