#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

import AutomizerPackage from "pptx-automizer";

const Automizer = AutomizerPackage.default;
const { modify } = AutomizerPackage;

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const APP_DIR = path.dirname(SCRIPT_DIR);
const TEMPLATE_DIR = path.join(APP_DIR, "presentation_templates");
const ROOT_TEMPLATE = "empty-root.pptx";
const BAPTISM_TEMPLATE = "normal-apostles-baptism.pptx";
const COMMUNION_TEMPLATE = "normal-apostles-communion.pptx";

const CREED_TEMPLATES = {
  "Apostles' Creed": {
    file: "normal-apostles.pptx",
    creedSlides: [33, 34, 35],
    postCreedBlank: 36,
    gloria: 37,
    specialMusic: 38,
    preSermonHymnBlank: 39,
    sermonHymnTitle: 40,
    sermonHymnVerse: 41,
    preSermonBlank: 44,
    sermon: 45,
    preClosingHymnBlank: 46,
    closingHymnTitle: 47,
    closingHymnVerse: 48,
    postClosingHymnBlank: 53,
    doxology: 54,
    finalBlank: 55,
  },
  "Nicene Creed": {
    file: "normal-nicene.pptx",
    creedSlides: [33, 34, 35, 36, 37, 38],
    postCreedBlank: 39,
    gloria: 40,
    specialMusic: 41,
    preSermonHymnBlank: 42,
    sermonHymnTitle: 43,
    sermonHymnVerse: 44,
    preSermonBlank: 47,
    sermon: 48,
    preClosingHymnBlank: 49,
    closingHymnTitle: 50,
    closingHymnVerse: 51,
    postClosingHymnBlank: 56,
    doxology: 57,
    finalBlank: 58,
  },
  "Athanasian Creed": {
    file: "normal-athanasian.pptx",
    creedSlides: [
      33, 34, 35, 36, 37, 38, 39, 40, 41,
      42, 43, 44, 45, 46, 47, 48, 49,
    ],
    postCreedBlank: 50,
    gloria: 51,
    specialMusic: 52,
    preSermonHymnBlank: 53,
    sermonHymnTitle: 54,
    sermonHymnVerse: 55,
    preSermonBlank: 58,
    sermon: 59,
    preClosingHymnBlank: 60,
    closingHymnTitle: 61,
    closingHymnVerse: 62,
    postClosingHymnBlank: 67,
    doxology: 68,
    finalBlank: 69,
  },
};

const COMMON = {
  blank: 1,
  callTitle: 2,
  callBody: 3,
  postCallBlank: 5,
  numberedHymnTitle: 6,
  openingHymnVerse: 7,
  postOpeningHymnBlank: 11,
  confessionSlides: [12, 13, 14, 15, 16],
  memoryTitle: 17,
  memoryBody: 18,
  postMemoryBlank: 19,
  firstLessonTitle: 20,
  firstLessonBody: 21,
  postFirstLessonBlank: 25,
  secondLessonTitle: 26,
  secondLessonBody: 27,
  postSecondLessonBlank: 31,
  gospelResponse: 32,
};

const OLD_TESTAMENT_BOOKS = new Set([
  "genesis", "exodus", "leviticus", "numbers", "deuteronomy", "joshua",
  "judges", "ruth", "1 samuel", "2 samuel", "1 kings", "2 kings",
  "1 chronicles", "2 chronicles", "ezra", "nehemiah", "esther", "job",
  "psalm", "psalms", "proverbs", "ecclesiastes", "song of solomon",
  "song of songs", "isaiah", "jeremiah", "lamentations", "ezekiel",
  "daniel", "hosea", "joel", "amos", "obadiah", "jonah", "micah",
  "nahum", "habakkuk", "zephaniah", "haggai", "zechariah", "malachi",
]);

const GOSPEL_BOOKS = new Set(["matthew", "mark", "luke", "john"]);

const EPISTLE_BOOKS = new Set([
  "romans", "1 corinthians", "2 corinthians", "galatians", "ephesians",
  "philippians", "colossians", "1 thessalonians", "2 thessalonians",
  "1 timothy", "2 timothy", "titus", "philemon", "hebrews", "james",
  "1 peter", "2 peter", "1 john", "2 john", "3 john", "jude",
]);

const BOOK_ALIASES = new Map([
  ["gen", "genesis"], ["ex", "exodus"], ["exod", "exodus"],
  ["lev", "leviticus"], ["num", "numbers"], ["deut", "deuteronomy"],
  ["josh", "joshua"], ["judg", "judges"], ["1 sam", "1 samuel"],
  ["2 sam", "2 samuel"], ["1 kgs", "1 kings"], ["2 kgs", "2 kings"],
  ["1 chr", "1 chronicles"], ["2 chr", "2 chronicles"],
  ["neh", "nehemiah"], ["esth", "esther"], ["ps", "psalm"],
  ["prov", "proverbs"], ["eccl", "ecclesiastes"], ["song", "song of songs"],
  ["isa", "isaiah"], ["jer", "jeremiah"], ["lam", "lamentations"],
  ["ezek", "ezekiel"], ["dan", "daniel"], ["hos", "hosea"],
  ["obad", "obadiah"], ["hab", "habakkuk"], ["zeph", "zephaniah"],
  ["zech", "zechariah"], ["mal", "malachi"], ["matt", "matthew"],
  ["mk", "mark"], ["lk", "luke"], ["jn", "john"], ["acts", "acts"],
  ["rom", "romans"], ["1 cor", "1 corinthians"], ["2 cor", "2 corinthians"],
  ["gal", "galatians"], ["eph", "ephesians"], ["phil", "philippians"],
  ["col", "colossians"], ["1 thess", "1 thessalonians"],
  ["2 thess", "2 thessalonians"], ["1 tim", "1 timothy"],
  ["2 tim", "2 timothy"], ["tit", "titus"], ["phlm", "philemon"],
  ["heb", "hebrews"], ["jas", "james"], ["1 pet", "1 peter"],
  ["2 pet", "2 peter"], ["1 jn", "1 john"], ["2 jn", "2 john"],
  ["3 jn", "3 john"], ["rev", "revelation"],
]);

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--output") {
      args.output = argv[index + 1];
      index += 1;
    } else {
      throw new Error(`Unknown argument: ${value}`);
    }
  }
  if (!args.output) throw new Error("--output is required");
  return args;
}

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

function normalizeBookName(reference) {
  const cleaned = plainText(reference)
    .toLowerCase()
    .replace(/[–—]/g, "-")
    .replace(/^the\s+/, "")
    .replace(/\./g, "")
    .replace(/\s+/g, " ")
    .trim();
  const match = cleaned.match(/^((?:[123]\s*)?[a-z]+(?:\s+of\s+[a-z]+|\s+[a-z]+)?)(?=\s+\d|\s*$)/);
  const candidate = match ? match[1].replace(/^(\d)([a-z])/, "$1 $2") : cleaned;
  return BOOK_ALIASES.get(candidate) ?? candidate;
}

export function lessonHeading(reference) {
  const book = normalizeBookName(reference);
  if (GOSPEL_BOOKS.has(book)) return "Gospel Lesson";
  if (EPISTLE_BOOKS.has(book)) return "Epistle Lesson";
  if (OLD_TESTAMENT_BOOKS.has(book)) return "Old Testament Lesson";
  return "New Testament Lesson";
}

function decodeEntities(text) {
  const named = {
    amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ",
    ldquo: "“", rdquo: "”", lsquo: "‘", rsquo: "’", ndash: "–", mdash: "—",
  };
  return text
    .replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (match, entity) => {
      if (entity.startsWith("#x")) return String.fromCodePoint(parseInt(entity.slice(2), 16));
      if (entity.startsWith("#")) return String.fromCodePoint(parseInt(entity.slice(1), 10));
      return named[entity.toLowerCase()] ?? match;
    });
}

export function plainText(value) {
  return decodeEntities(String(value ?? ""))
    .replace(/<\s*br\s*\/?\s*>/gi, "\n")
    .replace(/<\s*\/\s*(?:p|div)\s*>/gi, "\n")
    .replace(/<[^>]*>/g, "")
    .replace(/\r\n?/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n[ \t]+/g, "\n")
    .trim();
}

export function displayReference(value) {
  return plainText(value)
    .replace(/\s*\((?=[^)]*(?:G-pg|Z-pg))[^)]*\)\s*$/i, "")
    .trim();
}

export function memoryVerseText(value) {
  const withoutVerseNumbers = String(value ?? "")
    .replace(/<sup\b[^>]*>[\s\S]*?<\/sup>/gi, "")
    .replace(
      /<span\b[^>]*class\s*=\s*["'][^"']*\bverse(?:-number|-num)?\b[^"']*["'][^>]*>[\s\S]*?<\/span>/gi,
      "",
    )
    .replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹]+/g, "");
  return plainText(withoutVerseNumbers)
    .replace(/^\s*\d{1,3}(?:[.:])?\s+(?=\p{L})/u, "")
    .trim();
}

export function splitProse(value, maxChars) {
  const text = plainText(value).replace(/\s+/g, " ").trim();
  if (!text) return [];
  const words = text.split(" ");
  const chunks = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (current && candidate.length > maxChars) {
      chunks.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

export function splitHymnVerses(value) {
  return hymnSections(value).verses;
}

function hymnSections(value) {
  const text = plainText(value);
  if (!text) return { verses: [], refrain: "" };
  const refrainBlocks = [];
  const verseBlocks = [];
  for (const block of text.split(/\n\s*\n+/).map((item) => item.trim()).filter(Boolean)) {
    if (/^(?:refrain|chorus)\s*:?\s*(?:\n|$)/i.test(block)) {
      refrainBlocks.push(block);
    } else {
      verseBlocks.push(block);
    }
  }
  let verses = verseBlocks;
  if (verses.length === 1) {
    verses = verses[0].split(/\n(?=\s*\d+\s+)/).map((verse) => verse.trim()).filter(Boolean);
  }
  return { verses, refrain: refrainBlocks.join("\n") };
}

function splitHymnLines(lines, maxChars, maxLines) {
  const slides = [];
  const fittedLines = lines.flatMap((line) => (
    line.length > maxChars ? splitProse(line, maxChars) : [line]
  ));
  let current = [];
  for (const line of fittedLines) {
    const candidate = [...current, line].join("\n");
    if (current.length && (current.length >= maxLines || candidate.length > maxChars)) {
      slides.push(current);
      current = [line];
    } else {
      current.push(line);
    }
  }
  if (current.length) slides.push(current);

  // Avoid a single-line continuation slide. Moving the prior line forward
  // preserves the verse wording and usually keeps its final poetic couplet
  // together. Respect the character limit in the unusual case of two very
  // long wrapped lines.
  if (slides.length > 1 && slides.at(-1).length === 1) {
    const previous = slides.at(-2);
    const orphan = slides.at(-1);
    const rebalanced = [previous.at(-1), orphan[0]].join("\n");
    if (previous.length > 1 && rebalanced.length <= maxChars) {
      orphan.unshift(previous.pop());
    }
  }
  return slides;
}

function formatVerseAndRefrain(verseLines, refrainLines, maxTotalLines) {
  const contentLines = verseLines.length + refrainLines.length;
  const targetLines = Math.min(maxTotalLines, Math.max(contentLines + 1, 10));
  const blankLines = Math.max(1, targetLines - contentLines);
  return `${verseLines.join("\n")}${"\n".repeat(blankLines + 1)}${refrainLines.join("\n")}`;
}

export function hymnSlideFontSize(value) {
  const text = String(value ?? "");
  const lineCount = text.split("\n").length;
  const characterCount = text.replace(/\s+/g, " ").trim().length;
  if (lineCount <= 7 && characterCount <= 240) return 40;
  if (lineCount <= 9 && characterCount <= 320) return 36;
  if (lineCount <= 11 && characterCount <= 400) return 32;
  if (lineCount <= 14 && characterCount <= 520) return 28;
  return 26;
}

export function splitScriptureVerses(value) {
  const marker = "\uE000";
  let detectedMarker = false;
  const insertMarker = () => {
    detectedMarker = true;
    return marker;
  };
  let marked = String(value ?? "")
    .replace(/<sup\b[^>]*>\s*\d{1,3}[a-z]?\s*<\/sup>/gi, insertMarker)
    .replace(
      /<span\b[^>]*class\s*=\s*["'][^"']*\bverse(?:-number|-num|num)?\b[^"']*["'][^>]*>[\s\S]*?<\/span>/gi,
      insertMarker,
    )
    .replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹]+/g, insertMarker);
  marked = plainText(marked);
  marked = marked.replace(
    /(^|\n)\s*\d{1,3}[a-z]?(?:[.:])?\s+(?=\p{L}|["'“‘])/gu,
    (_match, prefix) => `${prefix}${insertMarker()}`,
  );
  marked = marked.replace(
    /([.!?;:])\s+\d{1,3}[a-z]?(?:[.:])?\s+(?=[A-Z“‘])/g,
    (_match, punctuation) => `${punctuation} ${insertMarker()}`,
  );

  const sourceUnits = detectedMarker
    ? marked.split(marker)
    : marked.split(/\n\s*\n+/);
  return sourceUnits
    .map((verse) => verse.replace(/\s+/g, " ").trim())
    .map((verse) => verse.replace(/^\d{1,3}[a-z]?(?:[.:])?\s+/, ""))
    .filter(Boolean);
}

export function scriptureSlideFontSize(value) {
  const length = plainText(value).replace(/\s+/g, " ").trim().length;
  if (length <= 345) return 40;
  if (length <= 400) return 34;
  if (length <= 470) return 32;
  if (length <= 550) return 30;
  if (length <= 650) return 28;
  if (length <= 760) return 26;
  if (length <= 900) return 24;
  if (length <= 1050) return 22;
  return 20;
}

export function splitScriptureSlideTexts(value, maxGroupChars = 430) {
  const verses = splitScriptureVerses(value);
  const chunks = [];
  let current = [];
  for (const verse of verses) {
    const candidate = [...current, verse].join(" ");
    if (current.length && candidate.length > maxGroupChars) {
      const text = current.join(" ");
      chunks.push({ text, fontSize: scriptureSlideFontSize(text) });
      current = [verse];
    } else {
      current.push(verse);
    }
  }
  if (current.length) {
    const text = current.join(" ");
    chunks.push({ text, fontSize: scriptureSlideFontSize(text) });
  }
  return chunks;
}

export function splitHymnSlideTexts(value, maxChars = 650, maxLines = 16) {
  const { verses, refrain } = hymnSections(value);
  if (!verses.length) return [];
  const slides = [];
  if (!refrain) {
    for (const verse of verses) {
      const lines = verse.split("\n").map((line) => line.trim()).filter(Boolean);
      for (const chunk of splitHymnLines(lines, maxChars, maxLines)) {
        slides.push(chunk.join("\n"));
      }
    }
    return slides;
  }

  const refrainLines = refrain.split("\n").map((line) => line.trim()).filter(Boolean);
  const maxTotalLines = Math.max(maxLines, 14);
  const maxTotalChars = Math.max(maxChars, 520);
  const maxVerseLines = Math.max(1, maxTotalLines - refrainLines.length - 1);
  const maxVerseChars = Math.max(80, maxTotalChars - refrain.length - 2);
  for (const verse of verses) {
    const lines = verse.split("\n").map((line) => line.trim()).filter(Boolean);
    for (const chunk of splitHymnLines(lines, maxVerseChars, maxVerseLines)) {
      slides.push(formatVerseAndRefrain(chunk, refrainLines, maxTotalLines));
    }
  }
  return slides;
}

function replaceLiteral(search, replacement) {
  return (element) => {
    const nodes = element.getElementsByTagName("a:t");
    const textNodes = [];
    for (let index = 0; index < nodes.length; index += 1) {
      const node = nodes.item(index);
      if (node) textNodes.push(node);
    }
    const combined = textNodes.map((node) => node.textContent ?? "").join("");
    const start = combined.indexOf(search);
    if (start < 0) throw new Error(`Template text not found: ${search}`);
    const end = start + search.length;
    let cursor = 0;
    let inserted = false;
    for (const node of textNodes) {
      const original = node.textContent ?? "";
      const nodeStart = cursor;
      const nodeEnd = cursor + original.length;
      cursor = nodeEnd;
      if (nodeEnd <= start || nodeStart >= end) continue;
      const prefix = nodeStart < start ? original.slice(0, start - nodeStart) : "";
      const suffix = nodeEnd > end ? original.slice(end - nodeStart) : "";
      if (!inserted) {
        node.textContent = `${prefix}${replacement}${suffix}`;
        inserted = true;
      } else {
        node.textContent = suffix;
      }
    }
  };
}

function setElementText(shapeName, text) {
  return (slide) => slide.modifyElement(shapeName, [modify.setText(text)]);
}

function setFontSize(fontSize) {
  const size = String(Math.round(fontSize * 100));
  return (element) => {
    for (const tag of ["a:rPr", "a:defRPr", "a:endParaRPr"]) {
      const nodes = element.getElementsByTagName(tag);
      for (let index = 0; index < nodes.length; index += 1) {
        nodes.item(index)?.setAttribute("sz", size);
      }
    }
  };
}

function setElementTextAndFont(shapeName, text, fontSize) {
  return (slide) => slide.modifyElement(
    shapeName,
    [modify.setText(text), setFontSize(fontSize)],
  );
}

function replaceElementText(shapeName, replacements) {
  return (slide) => slide.modifyElement(
    shapeName,
    replacements.map(([search, replacement]) => replaceLiteral(search, replacement)),
  );
}

function composeCallbacks(...callbacks) {
  return (slide) => {
    for (const callback of callbacks) callback(slide);
  };
}

function addSlide(presentation, number, callback, source = "source") {
  presentation.addSlide(source, number, callback);
}

function addHymnTitle(
  presentation,
  hymn,
  numberedSlide,
  unnumberedSlide,
  sourceNumber,
  sourceTitle,
) {
  const number = plainText(hymn?.num);
  const title = plainText(hymn?.title);
  if (!title) throw new Error("Each Grace hymn needs a title before generating the PowerPoint.");
  if (number) {
    addSlide(
      presentation,
      numberedSlide,
      replaceElementText("Title 1", [[sourceNumber, `#${number}`], [sourceTitle, title]]),
    );
  } else {
    addSlide(
      presentation,
      unnumberedSlide,
      replaceElementText("Title 1", [["Speak, O Lord", title]]),
    );
  }
}

function addHymnVerses(presentation, text, sourceSlide) {
  const verses = splitHymnSlideTexts(text);
  if (!verses.length) throw new Error("Each Grace hymn needs at least one verse for the PowerPoint.");
  for (const verse of verses) {
    addSlide(
      presentation,
      sourceSlide,
      setElementTextAndFont("Title 1", verse, hymnSlideFontSize(verse)),
    );
  }
}

function requireText(value, label) {
  const text = plainText(value);
  if (!text) throw new Error(`${label} is required before generating the PowerPoint.`);
  return text;
}

export async function generatePresentation(blob, outputPath) {
  const weekly = blob?.weekly ?? {};
  const largePrint = weekly?.large_print ?? {};
  const template = CREED_TEMPLATES[weekly.confession_of_faith];
  if (!template) throw new Error("Select the Apostles’, Nicene, or Athanasian Creed before generating the PowerPoint.");

  const lessons = Array.isArray(weekly.scripture_lessons) ? weekly.scripture_lessons : [];
  if (lessons.length < 2) throw new Error("Add two scripture lesson references before generating the PowerPoint.");
  const firstReference = requireText(lessons[0]?.[0], "First scripture lesson reference");
  const secondReference = requireText(lessons[1]?.[0], "Second scripture lesson reference");
  const sermonReference = requireText(
    displayReference(weekly.sermon_text),
    "Sermon scripture reference",
  );
  const firstHeading = lessonHeading(firstReference);
  const secondHeading = lessonHeading(secondReference);

  const callReference = requireText(weekly.call_to_worship, "Call to Worship reference");
  const callChunks = splitScriptureSlideTexts(largePrint.call_to_worship_text, 340);
  const memoryReference = requireText(weekly.memory_verse_ref, "Memory Verse reference");
  const memoryChunks = splitScriptureSlideTexts(weekly.memory_verse_text, 300);
  const firstLessonChunks = splitScriptureSlideTexts(largePrint.first_lesson_text);
  const secondLessonChunks = splitScriptureSlideTexts(largePrint.second_lesson_text);
  if (!callChunks.length) throw new Error("Call to Worship full text is required before generating the PowerPoint.");
  if (!memoryChunks.length) throw new Error("Memory Verse text is required before generating the PowerPoint.");
  if (!firstLessonChunks.length || !secondLessonChunks.length) {
    throw new Error("Both full scripture lesson texts are required before generating the PowerPoint.");
  }

  const outputDir = path.dirname(outputPath);
  const outputName = path.basename(outputPath);
  await fs.mkdir(outputDir, { recursive: true });

  const automizer = new Automizer({
    templateDir: TEMPLATE_DIR,
    outputDir,
    autoImportSlideMasters: true,
    removeExistingSlides: false,
    cleanup: true,
    cleanupPlaceholders: false,
    compression: 6,
    verbosity: 0,
  });
  const presentation = automizer
    .loadRoot(ROOT_TEMPLATE)
    .load(template.file, "source")
    .load(BAPTISM_TEMPLATE, "baptism")
    .load(COMMUNION_TEMPLATE, "communion");

  // The neutral root contributes the opening blank slide. Keeping it avoids
  // dangling root-slide relationships in older PowerPoint runtimes.
  addSlide(
    presentation,
    COMMON.callTitle,
    replaceElementText("Rectangle 3", [["Psalm 18:1-6", callReference]]),
  );
  for (const chunk of callChunks) {
    addSlide(
      presentation,
      COMMON.callBody,
      setElementTextAndFont("Content Placeholder 2", chunk.text, chunk.fontSize),
    );
  }
  addSlide(presentation, COMMON.postCallBlank);

  addHymnTitle(
    presentation,
    weekly.opening_hymn?.grace,
    COMMON.numberedHymnTitle,
    template.sermonHymnTitle,
    "#143",
    "Christ Is Made The Sure Foundation",
  );
  addHymnVerses(presentation, largePrint.opening_hymn_text, COMMON.openingHymnVerse);
  addSlide(presentation, COMMON.postOpeningHymnBlank);

  if (weekly.baptism?.enabled) {
    const baptismName = requireText(weekly.baptism?.text, "Baptism name");
    addSlide(
      presentation,
      12,
      replaceElementText("Title 1", [["Alora Christensen", baptismName]]),
      "baptism",
    );
    addSlide(presentation, 13, undefined, "baptism");
  }

  for (const slideNumber of COMMON.confessionSlides) addSlide(presentation, slideNumber);

  addSlide(
    presentation,
    COMMON.memoryTitle,
    replaceElementText("Title 1", [["Haggai 1:5", memoryReference]]),
  );
  for (const chunk of memoryChunks) {
    addSlide(
      presentation,
      COMMON.memoryBody,
      composeCallbacks(
        replaceElementText("Title 1", [["Haggai 1:5", memoryReference]]),
        replaceElementText("Content Placeholder 2", [[
          "Now, therefore, thus says the Lord of hosts: Consider your ways. ",
          chunk.text,
        ]]),
      ),
    );
  }
  addSlide(presentation, COMMON.postMemoryBlank);

  addSlide(
    presentation,
    COMMON.firstLessonTitle,
    replaceElementText("Content Placeholder 2", [
      ["Old Testament Lesson", firstHeading],
      ["Job 38:4-18", firstReference],
    ]),
  );
  for (const chunk of firstLessonChunks) {
    addSlide(
      presentation,
      COMMON.firstLessonBody,
      composeCallbacks(
        replaceElementText("Title 1", [
          ["Old Testament Lesson", firstHeading],
          ["Job 38:4-18", firstReference],
        ]),
        setElementTextAndFont("Content Placeholder 2", chunk.text, chunk.fontSize),
      ),
    );
  }
  addSlide(presentation, COMMON.postFirstLessonBlank);

  addSlide(
    presentation,
    COMMON.secondLessonTitle,
    replaceElementText("Title 1", [
      ["Gospel Lesson", secondHeading],
      ["Matthew 14:22-33", secondReference],
    ]),
  );
  for (const chunk of secondLessonChunks) {
    addSlide(
      presentation,
      COMMON.secondLessonBody,
      composeCallbacks(
        replaceElementText("Title 1", [
          ["Gospel Lesson", secondHeading],
          ["Matthew 14:22-33", secondReference],
        ]),
        setElementTextAndFont("Content Placeholder 2", chunk.text, chunk.fontSize),
      ),
    );
  }
  addSlide(presentation, COMMON.postSecondLessonBlank);
  addSlide(presentation, COMMON.gospelResponse);

  for (const slideNumber of template.creedSlides) addSlide(presentation, slideNumber);
  addSlide(presentation, template.postCreedBlank);
  addSlide(presentation, template.gloria);
  addSlide(presentation, template.specialMusic);
  addSlide(presentation, template.preSermonHymnBlank);

  addHymnTitle(
    presentation,
    weekly.sermon_hymn?.grace,
    template.closingHymnTitle,
    template.sermonHymnTitle,
    "#154",
    "Jesus Shall Reign",
  );
  addHymnVerses(presentation, largePrint.sermon_hymn_text, template.sermonHymnVerse);
  addSlide(presentation, template.preSermonBlank);
  addSlide(
    presentation,
    template.sermon,
    replaceElementText("Title 1", [["Romans 10:5-17", sermonReference]]),
  );
  addSlide(presentation, template.preClosingHymnBlank);

  addHymnTitle(
    presentation,
    weekly.closing_hymn?.grace,
    template.closingHymnTitle,
    template.sermonHymnTitle,
    "#154",
    "Jesus Shall Reign",
  );
  addHymnVerses(presentation, largePrint.closing_hymn_text, template.closingHymnVerse);
  addSlide(presentation, template.postClosingHymnBlank);

  if (weekly.communion?.enabled && weekly.communion?.grace) {
    addSlide(
      presentation,
      54,
      undefined,
      "communion",
    );
    addSlide(presentation, 55, undefined, "communion");
  }

  addSlide(presentation, template.doxology);
  addSlide(presentation, template.finalBlank);
  await presentation.write(outputName);
  return outputPath;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const input = JSON.parse(await readStdin());
  await generatePresentation(input, path.resolve(args.output));
  process.stdout.write(`${JSON.stringify({ ok: true, output: path.resolve(args.output) })}\n`);
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) {
  main().catch((error) => {
    process.stderr.write(`${error?.stack ?? error}\n`);
    process.exitCode = 1;
  });
}
