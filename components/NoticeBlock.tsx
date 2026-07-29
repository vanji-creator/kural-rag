"use client";

export interface NoticeAction {
  tag: string;
  label: string;
  lang: string;
  font: string;
  fontSize: string;
  onRun: () => void;
}

export interface Notice {
  kind: string;
  meta: string;
  text: string;
  actions?: NoticeAction[];
}

/**
 * The band above an answer that says what is wrong with it.
 *
 * This exists because the most dangerous output this product can produce is a
 * confident answer built from weak retrieval. Where the interface is unsure,
 * it says so in the same visual weight as the answer itself, not in a
 * footnote underneath.
 */
export function NoticeBlock({ notice }: { notice: Notice }) {
  return (
    <div className="notice">
      <div className="notice__head">
        <span lang="en" className="notice__kind">
          {notice.kind}
        </span>
        {notice.meta && <span className="notice__meta">{notice.meta}</span>}
      </div>

      <p lang="en" className="notice__text">
        {notice.text}
      </p>

      {notice.actions && notice.actions.length > 0 && (
        <div className="notice__actions">
          {notice.actions.map((action) => (
            <button
              key={action.label}
              type="button"
              className="notice__action"
              lang={action.lang}
              onClick={action.onRun}
            >
              <span
                style={{
                  fontFamily: "var(--f-mono)",
                  fontSize: 10,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  opacity: 0.75,
                }}
              >
                {action.tag}
              </span>
              <span style={{ fontFamily: action.font, fontSize: action.fontSize }}>
                {action.label}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
