import Link from "next/link";
import { notFound } from "next/navigation";

import { CopyLinkButton } from "@/components/CopyLinkButton";
import { altTranslations, commentaries, meanings } from "@/lib/apparatus";
import { CORPUS_SIZE, chapterNumberOf, getChapter, getKural } from "@/lib/corpus";

interface VersePageProps {
  params: Promise<{ number: string }>;
}

export async function generateMetadata({ params }: VersePageProps) {
  const { number } = await params;
  const kural = getKural(Number(number));
  if (!kural) return { title: "Not found — Kural RAG" };

  return {
    title: `குறள் ${kural.number} · ${kural.chapter_tamil} — Kural RAG`,
    description: kural.english_explanation,
  };
}

export default async function VersePage({ params }: VersePageProps) {
  const { number } = await params;
  const kuralNumber = Number(number);
  const kural = getKural(kuralNumber);
  if (!kural) notFound();

  const chapterNumber = chapterNumberOf(kural.number);
  const chapter = getChapter(chapterNumber);
  const positionInChapter = ((kural.number - 1) % 10) + 1;

  const previousNumber = kural.number > 1 ? kural.number - 1 : null;
  const nextNumber = kural.number < CORPUS_SIZE ? kural.number + 1 : null;

  return (
    <div className="page page--narrow">
      <section className="verse">
        <nav className="crumbs" aria-label="Where this verse sits">
          <Link href="/browse" className="crumbs__link">
            <span lang="en">← browse</span>
          </Link>
          <span aria-hidden="true" className="crumbs__sep">
            /
          </span>
          <span lang="ta" className="crumbs__ta">
            {kural.section_tamil}
          </span>
          <span aria-hidden="true" className="crumbs__sep">
            /
          </span>
          <span lang="ta" className="crumbs__ta">
            {kural.subsection_tamil}
          </span>
          <span aria-hidden="true" className="crumbs__sep">
            /
          </span>
          <Link
            href={`/browse?chapter=${chapterNumber}#chapter`}
            className="crumbs__link crumbs__ta"
            lang="ta"
          >
            {kural.chapter_tamil}
          </Link>
        </nav>

        <div data-anim className="verse__body">
          <div className="verse__head">
            <span className="verse__num">{kural.number}</span>
            <div className="verse__meta">
              <span lang="en" className="eyebrow eyebrow--muted eyebrow--small">
                chapter {chapterNumber} · {kural.chapter_tamil} · verse{" "}
                {positionInChapter} of 10
              </span>
              <span lang="en" className="verse__chap-en">
                {kural.chapter_english}
              </span>
            </div>

            <div className="verse__nav">
              {previousNumber ? (
                <Link
                  href={`/kural/${previousNumber}`}
                  className="verse__nav-button"
                  aria-label={`Kural ${previousNumber}`}
                >
                  ←
                </Link>
              ) : (
                <span className="verse__nav-button" style={{ opacity: 0.35 }}>
                  ←
                </span>
              )}
              {nextNumber ? (
                <Link
                  href={`/kural/${nextNumber}`}
                  className="verse__nav-button"
                  aria-label={`Kural ${nextNumber}`}
                >
                  →
                </Link>
              ) : (
                <span className="verse__nav-button" style={{ opacity: 0.35 }}>
                  →
                </span>
              )}
            </div>
          </div>

          <div className="verse__couplet">
            <p lang="ta" className="verse__line">
              {kural.kural_line1}
            </p>
            <p lang="ta" className="verse__line">
              {kural.kural_line2}
            </p>
            <p lang="en" className="verse__translit">
              {kural.transliteration}
            </p>
          </div>

          <div className="verse__block">
            <div className="railhead">
              <span lang="en" className="eyebrow">
                In English
              </span>
              <span className="rail" aria-hidden="true" />
            </div>

            <p lang="en" className="verse__prose">
              {kural.english_explanation}
            </p>

            <div className="verse__alts">
              {altTranslations(kural).map((translation) => (
                <div key={translation.label} className="verse__alt">
                  <span lang="en" className="eyebrow eyebrow--muted eyebrow--small">
                    {translation.label}
                  </span>
                  <p lang="en" className="verse__alt-text">
                    {translation.text}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="verse__block">
            <div className="railhead">
              <span lang="ta" style={{ fontFamily: "var(--f-ta-ui)", fontSize: 15, color: "var(--ink-2)" }}>
                உரை
              </span>
              <span lang="en" className="eyebrow eyebrow--muted eyebrow--small">
                Modern Tamil prose · three editors
              </span>
              <span className="rail" aria-hidden="true" />
            </div>

            {meanings(kural).map((meaning) => (
              <div key={meaning.who} className="verse__meaning">
                <span lang="ta" className="verse__meaning-who">
                  {meaning.who}
                </span>
                <p lang="ta" className="verse__meaning-text">
                  {meaning.text}
                </p>
              </div>
            ))}
          </div>

          <div className="verse__block">
            <div className="railhead">
              <span lang="ta" style={{ fontFamily: "var(--f-ta-ui)", fontSize: 15, color: "var(--ink-2)" }}>
                பழைய உரை
              </span>
              <span lang="en" className="eyebrow eyebrow--muted eyebrow--small">
                Classical commentary · exists in Tamil only
              </span>
              <span className="rail" aria-hidden="true" />
            </div>

            {commentaries(kural).map((commentary) => (
              <div key={commentary.who} className="verse__commentary">
                <div className="commentary__head">
                  <span lang="ta" className="verse__commentary-who">
                    {commentary.who}
                  </span>
                  <span lang="en" className="commentary__era">
                    {commentary.era}
                  </span>
                  <span className="commentary__len">{commentary.length}</span>
                </div>

                {commentary.hasChapterPreamble && (
                  <div className="commentary__preamble-note">
                    <span lang="ta">
                      அதிகாரமுன்னுரையுடன் தொடங்குகிறது
                    </span>
                    <span lang="en" className="eyebrow eyebrow--muted eyebrow--small">
                      This commentary opens with the chapter preamble, before the
                      gloss on the verse itself
                    </span>
                  </div>
                )}

                {commentary.text ? (
                  <p lang="ta" className="verse__commentary-text">
                    {commentary.text}
                  </p>
                ) : (
                  <p lang="en" className="commentary__missing">
                    No commentary by this author survives for this kural. The
                    verse is complete without it.
                  </p>
                )}
              </div>
            ))}
          </div>

          {kural.hand_sourced_fields.length > 0 && (
            <p lang="en" className="method__note">
              Sourced by hand for this verse, because no machine-readable source
              carried it: {kural.hand_sourced_fields.join(", ")}.
            </p>
          )}

          <div className="verse__foot">
            <span className="verse__permalink">/kural/{kural.number}</span>
            <CopyLinkButton />
            {chapter && (
              <Link
                href={`/?q=${encodeURIComponent(chapter.english)}`}
                className="button-solid"
              >
                <span lang="en">Ask about this chapter</span>
              </Link>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
