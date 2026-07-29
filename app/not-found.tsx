import Link from "next/link";

export default function NotFound() {
  return (
    <div className="page page--narrow">
      <section className="failure">
        <span aria-hidden="true" className="failure__glyph">
          ?
        </span>
        <h2 lang="en" className="failure__title">
          There is no such verse.
        </h2>
        <p lang="en" className="failure__body">
          The Thirukkural has exactly 1330 couplets, numbered 1 to 1330. Nothing
          lives outside that range.
        </p>
        <div className="failure__actions">
          <Link href="/browse" className="button-solid">
            <span lang="en">Browse the 133 chapters</span>
          </Link>
          <Link href="/" className="button-outline">
            <span lang="en">Ask a question instead</span>
          </Link>
        </div>
      </section>
    </div>
  );
}
