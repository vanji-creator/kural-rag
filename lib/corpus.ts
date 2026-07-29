import "server-only";

import rawKurals from "@/data/kurals.json";
import type { Chapter, Kural, Section, Subsection } from "./types";

/**
 * The corpus, loaded once.
 *
 * This is a static import, so the JSON goes through the bundler at build time
 * and lives in the server bundle. It must never be imported from a client
 * component — 5 MB is not something to send to a browser. `server-only` above
 * turns that mistake into a build error instead of a slow page.
 */
export const allKurals: Kural[] = rawKurals as unknown as Kural[];

/** Every chapter is exactly 10 verses, so the chapter number is arithmetic. */
export function chapterNumberOf(kuralNumber: number): number {
  return Math.ceil(kuralNumber / 10);
}

const kuralsByNumber = new Map<number, Kural>(
  allKurals.map((kural) => [kural.number, kural]),
);

export function getKural(kuralNumber: number): Kural | undefined {
  return kuralsByNumber.get(kuralNumber);
}

export function getKurals(kuralNumbers: number[]): Kural[] {
  return kuralNumbers
    .map((kuralNumber) => kuralsByNumber.get(kuralNumber))
    .filter((kural): kural is Kural => kural !== undefined);
}

/**
 * The 133 chapters, built from the corpus rather than from a hardcoded list.
 *
 * Two chapters share the same English title ("Reading the Signs"), so nothing
 * here may key off the title. Chapter number is the identity.
 */
export const allChapters: Chapter[] = buildChapters();

function buildChapters(): Chapter[] {
  const chapters: Chapter[] = [];

  for (const kural of allKurals) {
    const chapterNumber = chapterNumberOf(kural.number);
    // the first kural of each chapter carries the chapter's own titles
    if (kural.number !== (chapterNumber - 1) * 10 + 1) continue;

    chapters.push({
      number: chapterNumber,
      tamil: kural.chapter_tamil,
      english: kural.chapter_english,
      sectionTamil: kural.section_tamil,
      sectionEnglish: kural.section_english,
      subsectionTamil: kural.subsection_tamil,
      subsectionEnglish: kural.subsection_english,
      firstKural: (chapterNumber - 1) * 10 + 1,
      lastKural: chapterNumber * 10,
    });
  }

  return chapters;
}

const chaptersByNumber = new Map<number, Chapter>(
  allChapters.map((chapter) => [chapter.number, chapter]),
);

export function getChapter(chapterNumber: number): Chapter | undefined {
  return chaptersByNumber.get(chapterNumber);
}

export function getChapterKurals(chapterNumber: number): Kural[] {
  const chapter = chaptersByNumber.get(chapterNumber);
  if (!chapter) return [];
  const kurals: Kural[] = [];
  for (let number = chapter.firstKural; number <= chapter.lastKural; number += 1) {
    const kural = kuralsByNumber.get(number);
    if (kural) kurals.push(kural);
  }
  return kurals;
}

/**
 * The three books, each holding its subsections, each holding its chapters.
 *
 * Built by walking the chapters in order and starting a new group whenever the
 * section or subsection name changes. The book is ordered, so consecutive runs
 * are all we need — no sorting, no lookup table to fall out of date.
 */
export const allSections: Section[] = buildSections();

function buildSections(): Section[] {
  const sections: Section[] = [];

  for (const chapter of allChapters) {
    let currentSection = sections[sections.length - 1];

    if (!currentSection || currentSection.tamil !== chapter.sectionTamil) {
      currentSection = {
        tamil: chapter.sectionTamil,
        english: chapter.sectionEnglish,
        firstChapter: chapter.number,
        lastChapter: chapter.number,
        subsections: [],
      };
      sections.push(currentSection);
    }
    currentSection.lastChapter = chapter.number;

    let currentSubsection: Subsection | undefined =
      currentSection.subsections[currentSection.subsections.length - 1];

    if (!currentSubsection || currentSubsection.tamil !== chapter.subsectionTamil) {
      currentSubsection = {
        tamil: chapter.subsectionTamil,
        english: chapter.subsectionEnglish,
        chapters: [],
      };
      currentSection.subsections.push(currentSubsection);
    }
    currentSubsection.chapters.push(chapter);
  }

  return sections;
}

/** Which of the three books a chapter belongs to, as an index into allSections. */
export function sectionIndexOfChapter(chapterNumber: number): number {
  const index = allSections.findIndex(
    (section) =>
      chapterNumber >= section.firstChapter && chapterNumber <= section.lastChapter,
  );
  return index === -1 ? 0 : index;
}

export const CORPUS_SIZE = allKurals.length;
export const CHAPTER_COUNT = allChapters.length;
export const SUBSECTION_COUNT = allSections.reduce(
  (total, section) => total + section.subsections.length,
  0,
);
export const SECTION_COUNT = allSections.length;
