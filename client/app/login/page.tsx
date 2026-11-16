"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabase";
import { useSession } from "../../lib/use-session";
import { BRAND } from "../../lib/brand";
import Mark from "../../components/Mark";
import "../shell.css";

const FLOW = ["Describe", "Find", "Research", "Draft", "Approve", "Send", "Replies"];

export default function Login() {
  const router = useRouter();
  const session = useSession();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (session) router.replace("/dashboard");
  }, [session, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    if (mode === "signin") {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) setError(error.message);
      else router.replace("/dashboard");
    } else {
      const { data, error } = await supabase.auth.signUp({ email, password });
      if (error) setError(error.message);
      else if (data.session) router.replace("/dashboard");
      else setNotice("Account created. Check your inbox to confirm your email, then sign in.");
    }
    setBusy(false);
  }

  return (
    <main className="auth">
      <aside className="auth-aside">
        <div className="brand"><Mark />{BRAND}</div>
        <div>
          <h1>Outreach that waits for your approval.</h1>
          <p>Describe who you want to reach. {BRAND} finds the companies, researches each one, finds the right person and drafts the email. Nothing is sent until you approve it.</p>
        </div>
        <ol className="flow" aria-label="How it works">
          {FLOW.map((f) => (<li key={f}>{f}</li>))}
        </ol>
        <div className="stripe" aria-hidden="true" />
      </aside>
      <section className="auth-main">
        <form className="auth-card" onSubmit={submit}>
          <h2>{mode === "signin" ? "Sign in" : "Create your account"}</h2>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" autoComplete={mode === "signin" ? "current-password" : "new-password"} minLength={6} required value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {error && <p className="msg err" role="alert">{error}</p>}
          {notice && <p className="msg" role="status">{notice}</p>}
          <button className="btn primary" type="submit" disabled={busy}>
            {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
          <p className="switch">
            {mode === "signin" ? "No account yet? " : "Already registered? "}
            <button type="button" onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); setNotice(""); }}>
              {mode === "signin" ? "Create one" : "Sign in"}
            </button>
          </p>
        </form>
      </section>
    </main>
  );
}
