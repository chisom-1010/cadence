"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "../lib/use-session";
import { BRAND } from "../lib/brand";
import Mark from "../components/Mark";
import "./shell.css";
import "./landing.css";

const EXAMPLES = [
  "Small freight companies in Togo, Benin and Ghana with their own trucks",
  "Private clinics in Lomé that still book appointments by phone",
  "Online shops in Lagos selling fashion, 5 to 50 staff",
];

const STEPS = [
  { name: "Describe", text: "Say who you want to reach in a sentence or two." },
  { name: "Find", text: "Cadence searches the web for companies that fit." },
  { name: "Research", text: "It reads each company's own website and notes what it does." },
  { name: "Draft", text: "It writes a short email that uses what it found." },
  { name: "Approve", text: "You read every email. Edit it, approve it or reject it." },
  { name: "Replies", text: "Answers are sorted, and interested ones are flagged." },
];

const TRUST = [
  {
    title: "Facts come from the page, not from memory",
    text: "The AI only writes what appears in text it fetched from the company's site. If a name or detail isn't there, it isn't used.",
  },
  {
    title: "People are named by the company",
    text: "Contacts come from the company's own team and about pages. Guessed email addresses are checked for a working mail server and labelled as guesses.",
  },
  {
    title: "Nothing is sent without you",
    text: "Drafts wait in the approval queue. An email can be sent once, and only after you approve it.",
  },
];

export default function Home() {
  const session = useSession();
  const router = useRouter();
  const [text, setText] = useState("");

  function start(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (text.trim()) sessionStorage.setItem("cadence.draft", text.trim());
    } catch {}
    router.push(session ? "/campaigns" : "/login");
  }

  return (
    <div className="landing">
      <header className="lp-nav">
        <Link href="/" className="brand" aria-label={`${BRAND} home`}><Mark />{BRAND}</Link>
        <nav className="lp-links" aria-label="Sections">
          <a href="#how">How it works</a>
          <a href="#trust">Why you can trust it</a>
        </nav>
        {session ? (
          <Link className="btn primary small" href="/dashboard">Open {BRAND}</Link>
        ) : (
          <div className="btnrow">
            <Link className="btn quiet small" href="/login">Sign in</Link>
            <Link className="btn primary small" href="/login">Get started</Link>
          </div>
        )}
      </header>

      <main>
        <section className="lp-hero">
          <h1>Find the right companies. Write the first email. You press send.</h1>
          <p className="lp-lead">
            Describe who you want to reach. {BRAND} finds the companies, researches each one, finds the right person and drafts the email. Nothing goes out until you approve it.
          </p>

          <form className="lp-prompt" onSubmit={start}>
            <label className="sr" htmlFor="who">Who do you want to reach?</label>
            <textarea
              id="who"
              rows={3}
              maxLength={2000}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Describe who you want to reach and what you sell…"
            />
            <div className="lp-prompt-foot">
              <span className="hint">{session ? "Opens a new campaign with this text." : "You'll create a free account next."}</span>
              <button className="btn primary" type="submit">Start a campaign</button>
            </div>
          </form>
          <div className="lp-chips" aria-label="Examples">
            {EXAMPLES.map((x) => (
              <button key={x} type="button" className="lp-chip" onClick={() => setText(x)}>{x}</button>
            ))}
          </div>
        </section>

        <section className="lp-slogan" aria-label="Summary">
          <p>Cold email, minus the guesswork and the copy-paste.</p>
        </section>

        <section id="how" className="lp-section">
          <div className="lp-head">
            <h2>From one sentence to a reviewed inbox</h2>
            <p>Six steps, each one visible. You can stop, edit or redo any of them.</p>
          </div>
          <ol className="lp-steps">
            {STEPS.map((s, i) => (
              <li key={s.name} className="lp-step">
                <span className="lp-n" aria-hidden="true">{i + 1}</span>
                <h3>{s.name}</h3>
                <p>{s.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="lp-section lp-split">
          <div>
            <h2>A draft you can read in ten seconds</h2>
            <p className="lp-copy">
              Every email is short, mentions something specific about the company, and ends with a single question. Next to it you see the facts it was built from, so you can check it before it goes.
            </p>
            <Link className="btn" href={session ? "/queue" : "/login"}>See the approval queue</Link>
          </div>
          <figure className="lp-letter" aria-label="Example draft">
            <figcaption>Example draft</figcaption>
            <p className="lp-to"><span>To</span> Ama Mensah, Operations lead</p>
            <p className="lp-subj">Fewer empty return trips at Kpalimé Freight</p>
            <p className="lp-body">
              Hello Ama, I saw on your site that Kpalimé Freight runs its own fleet between Lomé and Accra. Our route planner matches return loads so those trucks don&apos;t come back empty. Would a short call next week be useful?
            </p>
            <p className="lp-basis">Built from: &ldquo;own fleet&rdquo; and &ldquo;Lomé to Accra&rdquo; on kpalimefreight.example/about</p>
          </figure>
        </section>

        <section id="trust" className="lp-section">
          <div className="lp-head">
            <h2>Built so it doesn&apos;t make things up</h2>
            <p>Outreach goes under your name. These rules keep it honest.</p>
          </div>
          <div className="lp-cards">
            {TRUST.map((t) => (
              <article key={t.title} className="lp-card">
                <h3>{t.title}</h3>
                <p>{t.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="lp-cta">
          <h2>Try it on your first campaign</h2>
          <p>It takes a sentence to start. You stay in control of every email.</p>
          <Link className="btn primary" href={session ? "/campaigns" : "/login"}>Start a campaign</Link>
        </section>
      </main>

      <footer className="lp-foot">
        <span className="brand"><Mark size={22} />{BRAND}</span>
        <span className="muted">AI outreach with a human in the loop.</span>
      </footer>
    </div>
  );
}
