"use client";

import Link from "next/link";
import { forwardRef } from "react";

import {
  altTranslations,
  chapterNumberOf,
  commentaries,
  meanings,
} from "@/lib/apparatus";
import type { Kural } from "@/lib/types";

interface ResultCardProps {
  kural: Kural;
  /** the raw retrieval score, 0..1 */
  score: number;
  /** 0-based position in the ranking */
  position: number;
  /** score to *render* — animates up from 0 so the ranking assembles itself */
  scoreProgress: number;
  /** the threshold at or above which this engine calls a match strong */
  highConfidence: number;
  isOpen: boolean;
  onToggle: () => void;
  /** true briefly after a citation scrolled the reader here */
  arrived: boolean;
  reducedMotion: boolean;
}

export const ResultCard = forwardRef<HTMLLIElement, ResultCardProps>(
  function ResultCard(
    {
      kural,
      score,
      position,
      scoreProgress,
      highConfidence,
      isOpen,
      onToggle,
      arrived,
      reducedMotion,
    },
    ref,
  ) {
    const shownScore = score * scoreProgress;
    const isStrong = score >= highConfidence;
    const panelId = `panel-${kural.number}`;

    const animation = reducedMotion
      ? "kr-fade 240ms linear both"
      : "kr-lift 640ms var(--e-out) both";
    const animationDelay = reducedMotion ? "0ms" : `${90 + position * 70}ms`;

    return (
      <li
        ref={ref}
        id={`kural-${kural.number}`}
        data-anim
        className={`result${arrived ? " result--arrived" : ""}`}
        style={{ animation, animationDelay }}
      >
        <div className="result__inner">
          <div className="result__head">
            <span className="result__rank">
              {String(position + 1).padStart(2, "0")}
            </span>

            <Link href={`/kural/${kural.number}`} className="result__id">
              <span className="result__num">{kural.number}</span>
              <span lang="ta" className="result__chap-ta">
                {kural.chapter_tamil}
              </span>
              <span lang="en" className="result__chap-en">
                {kural.chapter_english}
              </span>
            </Link>

            <div className="result__score">
              <span className="scorebar" aria-hidden="true">
                <span
                  className="scorebar__fill"
                  style={{
                    width: `${(shownScore * 100).toFixed(1)}%`,
                    background: isStrong ? "var(--accent)" : "var(--ink-4)",
                  }}
                />
              </span>
              <span
                className="result__score-text"
                style={{ color: isStrong ? "var(--ink)" : "var(--ink-3)" }}
              >
                {shownScore.toFixed(2)}
              </span>
            </div>
          </div>

          <div className="result__text">
            <div className="couplet">
              <p lang="ta" className="couplet__line">
                {kural.kural_line1}
              </p>
              <p lang="ta" className="couplet__line">
                {kural.kural_line2}
              </p>
              <p lang="en" className="couplet__translit">
                {kural.transliteration}
              </p>
            </div>
            <p lang="en" className="result__primary">
              {kural.english_explanation}
            </p>
          </div>

          <div className="result__actions">
            <button
              type="button"
              className="disclose"
              onClick={onToggle}
              aria-expanded={isOpen}
              aria-controls={panelId}
            >
              <span className="disclose__chevron" aria-hidden="true"
                style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0deg)" }}>
                ↓
              </span>
              <span lang="en">
                {isOpen
                  ? "Hide commentary and translations"
                  : "Commentary, translations, உரை"}
              </span>
            </button>

            <Link href={`/kural/${kural.number}`} className="linkish">
              <span lang="en">Full verse page →</span>
            </Link>

            {arrived && (
              <span className="result__arrived">
                <span aria-hidden="true">⟨{kural.number}⟩</span>
                <span lang="en">you arrived here from the citation</span>
              </span>
            )}
          </div>

          <div
            id={panelId}
            className={`panel${isOpen ? " panel--open" : ""}`}
            // hidden from assistive tech and from tab order while collapsed
            aria-hidden={!isOpen}
          >
            <div className="panel__clip">
              <div className="panel__inner" inert={!isOpen}>
                <div className="alt-translations">
                  {altTranslations(kural).map((translation) => (
                    <div key={translation.label} className="alt-translation">
                      <span lang="en" className="eyebrow eyebrow--muted eyebrow--small">
                        {translation.label}
                      </span>
                      <p lang="en" className="alt-translation__text">
                        {translation.text}
                      </p>
                    </div>
                  ))}
                </div>

                <div className="meanings">
                  <div className="railhead">
                    <span lang="ta" style={{ fontFamily: "var(--f-ta-ui)", fontSize: 14, color: "var(--ink-2)" }}>
                      உரை
                    </span>
                    <span lang="en" className="eyebrow eyebrow--muted eyebrow--small">
                      Modern Tamil prose
                    </span>
                    <span className="rail rail--faint" aria-hidden="true" />
                  </div>
                  <div className="meanings__list">
                    {meanings(kural).map((meaning) => (
                      <div key={meaning.who} className="meaning">
                        <span lang="ta" className="meaning__who">
                          {meaning.who}
                        </span>
                        <p lang="ta" className="meaning__text">
                          {meaning.text}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="commentaries">
                  <div className="railhead">
                    <span lang="ta" style={{ fontFamily: "var(--f-ta-ui)", fontSize: 14, color: "var(--ink-2)" }}>
                      பழைய உரை
                    </span>
                    <span lang="en" className="eyebrow eyebrow--muted eyebrow--small">
                      Classical commentary · Tamil only, no English exists
                    </span>
                    <span className="rail rail--faint" aria-hidden="true" />
                  </div>

                  {commentaries(kural).map((commentary) => (
                    <div key={commentary.who} className="commentary">
                      <div className="commentary__head">
                        <span lang="ta" className="commentary__who">
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
                            அதிகாரமுன்னுரையுடன் தொடங்குகிறது · opens with the
                            chapter preamble, before the verse gloss
                          </span>
                        </div>
                      )}

                      {commentary.text ? (
                        <p lang="ta" className="commentary__text">
                          {commentary.text}
                        </p>
                      ) : (
                        <p lang="en" className="commentary__missing">
                          No commentary by this author survives for this kural.
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </li>
    );
  },
);
