import type { Metadata } from "next";
import {
  Anek_Tamil,
  IBM_Plex_Mono,
  Instrument_Sans,
  Noto_Serif_Tamil,
  Spectral,
} from "next/font/google";

import { Masthead } from "@/components/Masthead";
import { Colophon } from "@/components/Colophon";
import { CORPUS_SIZE } from "@/lib/corpus";

import "./globals.css";

/*
 * Five faces, two scripts, one grid.
 *
 * The Tamil and Latin faces are chosen as a matched pair, not picked
 * separately: Tamil letterforms are taller and need far more line height
 * (1.85–2.1 against 1.5–1.7) or the vowel signs that hang above and below
 * collide with the next line. Every Tamil rule in globals.css leads with
 * line-height for that reason.
 */

const spectral = Spectral({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  style: ["normal", "italic"],
  variable: "--font-spectral",
  display: "swap",
});

const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-instrument-sans",
  display: "swap",
});

const notoSerifTamil = Noto_Serif_Tamil({
  subsets: ["tamil"],
  variable: "--font-noto-serif-tamil",
  display: "swap",
});

const anekTamil = Anek_Tamil({
  subsets: ["tamil"],
  variable: "--font-anek-tamil",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-ibm-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Kural RAG — ask the Thirukkural a question",
  description:
    "Semantic search over all 1330 kurals, with word-by-word meaning and classical commentary. Every answer cites the verses it was built from.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const fontVariables = [
    spectral.variable,
    instrumentSans.variable,
    notoSerifTamil.variable,
    anekTamil.variable,
    ibmPlexMono.variable,
  ].join(" ");

  return (
    <html lang="en" className={fontVariables}>
      <body>
        <div className="shell">
          <Masthead corpusSize={CORPUS_SIZE} />
          <main>{children}</main>
          <Colophon />
        </div>
      </body>
    </html>
  );
}
