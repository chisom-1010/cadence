"use client";

import { Suspense, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabase";
import { useSession } from "../../lib/use-session";
import { BRAND } from "../../lib/brand";
import NavLinks from "../../components/NavLinks";
import Mark from "../../components/Mark";
import "../shell.css";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const router = useRouter();

  useEffect(() => {
    if (session === null) router.replace("/login");
  }, [session, router]);

  if (!session) return <div className="boot">Loading…</div>;

  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand"><Mark />{BRAND}</div>
        <Suspense fallback={<nav className="nav" aria-label="Main" />}>
          <NavLinks />
        </Suspense>
        <div className="who">
          <span>{session.user.email}</span>
          <button className="btn small quiet" onClick={() => supabase.auth.signOut()}>Sign out</button>
        </div>
      </aside>
      <main className="main">
        <Suspense fallback={<p className="muted">Loading…</p>}>{children}</Suspense>
      </main>
    </div>
  );
}
