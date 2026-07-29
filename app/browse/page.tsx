import Link from "next/link";

import {
  CHAPTER_COUNT,
  CORPUS_SIZE,
  SECTION_COUNT,
  SUBSECTION_COUNT,
  allSections,
  getChapter,
  getChapterKurals,
  sectionIndexOfChapter,
} from "@/lib/corpus";

export const metadata = {
  title: "Browse — Kural RAG",
  description:
    "The Thirukkural as an object: 3 sections, 13 subsections, 133 chapters of 10 verses.",
};

/**
 * The book, laid out as a book.
 *
 * Which section is open and which chapter is expanded live in the URL rather
 * than in component state, so any chapter can be linked to directly and the
 * back button behaves. No client JavaScript is involved on this page at all.
 */
export default async function BrowsePage({
  searchParams,
}: {
  searchParams: Promise<{ section?: string; chapter?: string }>;
}) {
  const params = await searchParams;

  const requestedChapter = Number(params.chapter);
  const openChapterNumber =
    Number.isInteger(requestedChapter) &&
    requestedChapter >= 1 &&
    requestedChapter <= CHAPTER_COUNT
      ? requestedChapter
      : null;

  const requestedSection = Number(params.section);
  const sectionIndex = Number.isInteger(requestedSection)
    ? Math.min(Math.max(requestedSection, 0), SECTION_COUNT - 1)
    : openChapterNumber
      ? sectionIndexOfChapter(openChapterNumber)
      : 0;

  const openSection = allSections[sectionIndex];
  const openChapter = openChapterNumber ? getChapter(openChapterNumber) : null;
  const openChapterKurals = openChapterNumber
    ? getChapterKurals(openChapterNumber)
    : [];

  return (
    <div className="page">
      <section className="browse">
        <div className="browse__intro">
          <span lang="en" className="eyebrow">
            The book as an object
          </span>
          <h2 className="display-title">
            <span lang="en">
              {SECTION_COUNT} sections, {SUBSECTION_COUNT} subsections,{" "}
              {CHAPTER_COUNT} chapters, 10 verses each.
            </span>
          </h2>
        </div>

        <div className="sections">
          {allSections.map((section, index) => {
            const isCurrent = index === sectionIndex;
            return (
              <Link
                key={section.tamil}
                href={`/browse?section=${index}`}
                className={`section-tab${isCurrent ? " section-tab--current" : ""}`}
                aria-current={isCurrent ? "true" : undefined}
              >
                <span className="section-tab__row">
                  <span lang="ta" className="section-tab__ta">
                    {section.tamil}
                  </span>
                  <span className="section-tab__range">
                    {section.firstChapter}–{section.lastChapter}
                  </span>
                </span>
                <span lang="en" className="section-tab__en">
                  {section.english}
                </span>
              </Link>
            );
          })}
        </div>

        <div className="subsections">
          {openSection.subsections.map((subsection) => (
            <div key={subsection.tamil} className="subsection">
              <div className="subsection__head">
                <span lang="ta" className="subsection__ta">
                  {subsection.tamil}
                </span>
                <span lang="en" className="subsection__en">
                  {subsection.english}
                </span>
                <span className="subsection__count">
                  {subsection.chapters.length} chapters
                </span>
              </div>

              <div className="chapter-grid">
                {subsection.chapters.map((chapter) => (
                  <Link
                    key={chapter.number}
                    href={`/browse?section=${sectionIndex}&chapter=${chapter.number}#chapter`}
                    className="chapter-tile"
                    aria-current={
                      chapter.number === openChapterNumber ? "page" : undefined
                    }
                  >
                    <span className="chapter-tile__row">
                      <span className="chapter-tile__n">
                        {String(chapter.number).padStart(3, "0")}
                      </span>
                      <span lang="ta" className="chapter-tile__ta">
                        {chapter.tamil}
                      </span>
                    </span>
                    <span className="chapter-tile__row">
                      <span className="chapter-tile__spacer" aria-hidden="true" />
                      <span lang="en" className="chapter-tile__en">
                        {chapter.english}
                      </span>
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>

        {openChapter && (
          <div id="chapter" data-anim className="chapter-open">
            <div className="chapter-open__head">
              <span className="chapter-open__n">
                {String(openChapter.number).padStart(3, "0")}
              </span>
              <div className="chapter-open__titles">
                <span lang="ta" className="chapter-open__ta">
                  {openChapter.tamil}
                </span>
                <span lang="en" className="chapter-open__en">
                  {openChapter.english}
                </span>
              </div>
              <span className="chapter-open__range">
                {openChapter.firstKural}–{openChapter.lastKural}
              </span>
            </div>

            <ol className="chapter-list">
              {openChapterKurals.map((kural, index) => (
                <li
                  key={kural.number}
                  data-anim
                  style={{
                    animation: "kr-lift 640ms var(--e-out) both",
                    animationDelay: `${90 + index * 70}ms`,
                  }}
                >
                  <Link href={`/kural/${kural.number}`} className="chapter-row">
                    <span className="chapter-row__n">{kural.number}</span>
                    <span className="chapter-row__body">
                      <span className="chapter-row__couplet">
                        <span lang="ta" className="chapter-row__line">
                          {kural.kural_line1}
                        </span>
                        <span lang="ta" className="chapter-row__line">
                          {kural.kural_line2}
                        </span>
                      </span>
                      <span lang="en" className="chapter-row__ex">
                        {kural.english_explanation}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          </div>
        )}

        {!openChapter && (
          <p lang="en" className="method__note">
            Pick a chapter to read its ten verses. All {CORPUS_SIZE} are here —
            nothing on this page is loaded on demand or sampled.
          </p>
        )}
      </section>
    </div>
  );
}
