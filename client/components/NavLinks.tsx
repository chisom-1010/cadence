"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/dashboard", label: "Today" },
  { href: "/campaigns", label: "Campaigns" },
  { href: "/leads", label: "Leads" },
  { href: "/queue", label: "Approval queue" },
  { href: "/replies", label: "Replies" },
];

export default function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="nav" aria-label="Main">
      {NAV.map((n) => {
        const active = pathname.startsWith(n.href);
        return (
          <Link key={n.href} href={n.href} className={active ? "active" : ""} aria-current={active ? "page" : undefined}>
            {n.label}
          </Link>
        );
      })}
    </nav>
  );
}
