"use client";

import { useState } from "react";

export function CopyLinkButton() {
  const [copied, setCopied] = useState(false);

  return (
    <button
      type="button"
      className="button-outline"
      style={{ marginLeft: "auto" }}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(window.location.href);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        } catch {
          // clipboard permission denied — say nothing rather than claim success
          setCopied(false);
        }
      }}
    >
      <span lang="en">{copied ? "Link copied" : "Copy link"}</span>
    </button>
  );
}
