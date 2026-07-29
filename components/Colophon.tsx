import Link from "next/link";

import { DEMO_LABELS } from "@/lib/demo";

/**
 * The "prototype states" row is deliberately kept from the design.
 *
 * Several screens — a strong answer, a low-confidence answer, a refusal —
 * cannot be produced on demand while the retrieval backend is a stand-in.
 * These links jump straight to each one, and anything reached this way is
 * marked as a demo state on the screen itself.
 */
export function Colophon() {
  return (
    <footer className="colophon">
      <div className="colophon__inner">
        <div className="colophon__top">
          <span lang="ta" className="colophon__ta">
            திருக்குறள்
          </span>
          <span lang="en" className="colophon__note">
            Public-domain text. Commentary is attributed to its editor on every
            screen, and the classical commentary is shown in Tamil because no
            English version of it exists.
          </span>
        </div>

        <div className="colophon__states">
          <span lang="en" className="eyebrow eyebrow--muted eyebrow--small">
            Prototype states
          </span>
          {DEMO_LABELS.map((demo) => (
            <Link key={demo.key} href={`/?demo=${demo.key}`} className="chip">
              <span lang="en">{demo.label}</span>
            </Link>
          ))}
          <Link href="/?state=error" className="chip">
            <span lang="en">backend error</span>
          </Link>
        </div>
      </div>
    </footer>
  );
}
