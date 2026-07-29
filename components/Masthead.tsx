"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Search" },
  { href: "/browse", label: "Browse" },
  { href: "/method", label: "Method" },
];

export function Masthead({ corpusSize }: { corpusSize: number }) {
  const pathname = usePathname();

  // a verse page is reached from Browse, so Browse stays lit while reading one
  const activeHref =
    pathname === "/"
      ? "/"
      : pathname.startsWith("/method")
        ? "/method"
        : pathname.startsWith("/browse") || pathname.startsWith("/kural")
          ? "/browse"
          : "";

  return (
    <header className="masthead">
      <Link href="/" className="masthead__mark" aria-label="Kural RAG — home">
        <span lang="ta" className="masthead__mark-ta">
          குறள்
        </span>
        <span className="masthead__divider" aria-hidden="true" />
        <span lang="en" className="masthead__mark-en">
          Kural&nbsp;RAG
        </span>
      </Link>

      <nav className="masthead__nav">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="navlink"
            aria-current={activeHref === item.href ? "page" : undefined}
          >
            <span lang="en">{item.label}</span>
            <span className="navlink__underline" aria-hidden="true" />
          </Link>
        ))}
        <span className="masthead__count">{corpusSize} verses</span>
      </nav>
    </header>
  );
}
