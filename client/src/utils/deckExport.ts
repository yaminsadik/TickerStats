/**
 * Deck export utilities - PDF and PPTX generation from DeckExportData.
 * Uses jsPDF for PDF and PptxGenJS for PowerPoint.
 */
import type { DeckExportData } from "../components/ui/JsonViewerModal";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toTitleCase(str: string) {
  return str.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

interface NormalizedSection {
  section_id: string;
  slides: Array<{
    slide_id?: string;
    title: string;
    bullets: Array<{ text: string; source_needed?: boolean }>;
    speaker_notes?: string;
    layout_hints?: {
      style?: string;
      suggested_visual?: string | null;
      max_bullets?: number;
    };
  }>;
  citations?: string[];
}

type NormalizedSlide = NormalizedSection["slides"][number];
type Bullet = NormalizedSlide["bullets"][number];

export type PptxDesignLayout =
  | "cards"
  | "two_column"
  | "timeline"
  | "swot"
  | "valuation"
  | "blueprint";

type PptxBlockType =
  | "hero_callout"
  | "metric_tile"
  | "bullet_card"
  | "text_box"
  | "timeline_item"
  | "two_column_panel"
  | "risk_box"
  | "valuation_callout"
  | "section_badge"
  | "comps_table"
  | "cover_block";

interface PptxLayoutBlock {
  type: PptxBlockType;
  x: number;
  y: number;
  w: number;
  h: number;
  text_source?: string;
  text_refs?: string[];
  static_text?: string[];
  label?: string;
  title?: string;
  body?: string;
  accent_color?: string;
  tone?: string;
  severity?: string;
  highlight_row_index?: number;
  style?: {
    fill?: string;
    text_color?: string;
    header_color?: string;
    border?: string;
    alignment?: "left" | "center" | "right";
  };
}

export interface PptxDesignSpec {
  version?: string;
  provider?: string;
  model?: string;
  cached?: boolean;
  theme?: Partial<{
    name: string;
    navy: string;
    blue: string;
    accent: string;
    bg: string;
    card: string;
    ink: string;
    text: string;
    muted: string;
    border: string;
    head_font_face: string;
    body_font_face: string;
  }>;
  slides?: Array<{
    section_id: string;
    slide_index: number;
    slide_id?: string | null;
    layout: PptxDesignLayout;
    archetype?: string;
    emphasis?: string;
    accent_color?: string;
    rationale?: string;
    blocks?: PptxLayoutBlock[];
    warnings?: string[];
  }>;
}

type PptxSlideDesign = NonNullable<PptxDesignSpec["slides"]>[number];

const DEFAULT_PPT = {
  w: 13.33,
  h: 7.5,
  navy: "172554",
  blue: "1E3A8A",
  accent: "38BDF8",
  bg: "F8FAFC",
  card: "FFFFFF",
  ink: "0F172A",
  text: "334155",
  muted: "64748B",
  border: "CBD5E1",
  green: "16A34A",
  red: "DC2626",
  amber: "D97706",
  purple: "7C3AED",
};

let PPT = DEFAULT_PPT;

const PDF = {
  navy: [23, 37, 84] as [number, number, number],
  blue: [30, 58, 138] as [number, number, number],
  accent: [56, 189, 248] as [number, number, number],
  bg: [248, 250, 252] as [number, number, number],
  card: [255, 255, 255] as [number, number, number],
  ink: [15, 23, 42] as [number, number, number],
  text: [51, 65, 85] as [number, number, number],
  muted: [100, 116, 139] as [number, number, number],
  border: [203, 213, 225] as [number, number, number],
};

function normalizeSections(data: DeckExportData): NormalizedSection[] {
  const appendCompsSection = (sections: NormalizedSection[]) => {
    const hasComps = Boolean((data as any).computed_inputs?.comps_table);
    const hasCompsSlide = sections.some((section) => {
      const sectionId = section.section_id.toLowerCase();
      if (sectionId === "comparable_companies" || sectionId === "comparables") return true;
      return (section.slides || []).some((slide) => /comparable|comp\b/i.test(slide.title));
    });
    if (!hasComps || hasCompsSlide) return sections;

    return [
      ...sections,
      {
        section_id: "comparable_companies",
        slides: [
          {
            slide_id: "comparable_companies_1",
            title: "Comparable Companies",
            bullets: [{ text: "Comparable-company trading metrics from computed market data." }],
            layout_hints: {
              style: "table",
              suggested_visual: "comps_table",
              max_bullets: 1,
            },
          },
        ],
        citations: [],
      },
    ];
  };

  if (data.results && data.results.length > 0) {
    return appendCompsSection(data.results as NormalizedSection[]);
  }
  if (data.sections && data.sections.length > 0) {
    return appendCompsSection(data.sections.map((s) => ({
      section_id: s.section_id,
      slides: s.slides as NormalizedSection["slides"],
      citations: s.citations,
    })));
  }
  return [];
}

function getGeneratedDate(data: DeckExportData) {
  return data.generated_at || data.metadata?.generated_at;
}

function getDeckTitle(data: DeckExportData) {
  const ticker = data.ticker || data.metadata?.ticker || "";
  const rawCompanyName = data.company_name || data.metadata?.company_name || "";
  const companyName = rawCompanyName && rawCompanyName !== ticker ? rawCompanyName : ticker;
  return { ticker, companyName };
}

function formatDate(iso: string | undefined): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "";
  }
}

function countSlidesAndSections(sections: NormalizedSection[]) {
  let slideCount = 0;
  for (const section of sections) {
    slideCount += (section.slides || []).length;
  }
  return { sectionCount: sections.length, slideCount };
}

function cleanText(text: string) {
  return text.replace(/\s+/g, " ").trim();
}

function isDisplayNullish(text: string): boolean {
  const t = cleanText(text).toLowerCase();
  return !t || t === "null" || t === "undefined" || t === "n/a" || t === "none";
}

function shortText(text: string, max = 145) {
  const cleaned = cleanText(text);
  return cleaned.length > max ? `${cleaned.slice(0, max - 1).trim()}...` : cleaned;
}

function stripPrefix(text: string) {
  return cleanText(
    text.replace(
      /^(what|who|products\/services|customers|revenue flow|near-term|thesis|market believes|we believe|would change mind|s|w|o|t):\s*/i,
      "",
    ),
  );
}

function cleanHex(value: string | undefined, fallback: string) {
  const cleaned = (value || "").replace(/^#/, "").trim();
  return /^[0-9A-Fa-f]{6}$/.test(cleaned) ? cleaned.toUpperCase() : fallback;
}

function mergePptTheme(spec?: PptxDesignSpec) {
  const theme = spec?.theme || {};
  return {
    ...DEFAULT_PPT,
    navy: cleanHex(theme.navy, DEFAULT_PPT.navy),
    blue: cleanHex(theme.blue, DEFAULT_PPT.blue),
    accent: cleanHex(theme.accent, DEFAULT_PPT.accent),
    bg: cleanHex(theme.bg, DEFAULT_PPT.bg),
    card: cleanHex(theme.card, DEFAULT_PPT.card),
    ink: cleanHex(theme.ink, DEFAULT_PPT.ink),
    text: cleanHex(theme.text, DEFAULT_PPT.text),
    muted: cleanHex(theme.muted, DEFAULT_PPT.muted),
    border: cleanHex(theme.border, DEFAULT_PPT.border),
  };
}

function getSlideDesign(
  spec: PptxDesignSpec | undefined,
  section: NormalizedSection,
  slide: NormalizedSlide,
  slideIndex: number,
): PptxSlideDesign | undefined {
  return spec?.slides?.find((item) => {
    if (item.section_id !== section.section_id) return false;
    if (item.slide_id && slide.slide_id && item.slide_id === slide.slide_id) return true;
    return item.slide_index === slideIndex;
  });
}

function slideKind(section: NormalizedSection, slide: NormalizedSlide) {
  const style = slide.layout_hints?.style?.toLowerCase() || "";
  const visual = slide.layout_hints?.suggested_visual?.toLowerCase() || "";
  const title = slide.title.toLowerCase();
  const sectionId = section.section_id.toLowerCase();
  const joined = `${sectionId} ${title} ${style} ${visual}`;

  if (joined.includes("timeline")) return "timeline";
  if (sectionId.includes("swot")) return "swot";
  if (joined.includes("valuation") || joined.includes("waterfall") || title.includes("price target")) {
    return "valuation";
  }
  if (style.includes("two_column") || title.includes("variant view") || title.includes("competitive")) {
    return "two_column";
  }
  if (
    style.includes("snapshot") ||
    visual.includes("chart") ||
    visual.includes("segment") ||
    title.includes("kpi") ||
    title.includes("capital structure")
  ) {
    return "cards";
  }
  return "cards";
}

function splitForColumns(bullets: Bullet[]) {
  const midpoint = Math.ceil(bullets.length / 2);
  return [bullets.slice(0, midpoint), bullets.slice(midpoint)];
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function blockBounds(block: PptxLayoutBlock) {
  const x = clamp(Number(block.x) || 0.65, 0.35, 12.45);
  const y = clamp(Number(block.y) || 1.55, 1.42, 6.7);
  const w = clamp(Number(block.w) || 3.6, 0.7, PPT.w - x - 0.3);
  const h = clamp(Number(block.h) || 1.0, 0.3, PPT.h - y - 0.45);
  return { x, y, w, h };
}

function sourceText(deckSlide: NormalizedSlide, source?: string) {
  const key = (source || "bullet_0").toLowerCase();
  if (key === "title") {
    const t = deckSlide.title || "";
    return isDisplayNullish(t) ? "" : t;
  }
  const match = key.match(/^bullet_(\d+)$/);
  if (match) {
    const bullet = deckSlide.bullets?.[Number(match[1])];
    if (!bullet) return "";
    const raw = stripPrefix(bullet.text);
    return isDisplayNullish(raw) ? "" : raw;
  }
  return "";
}

function resolveTextRefs(deckSlide: NormalizedSlide, refs?: string[]) {
  return (refs || [])
    .map((ref) => sourceText(deckSlide, ref))
    .filter((t) => Boolean(t) && !isDisplayNullish(t));
}

function tokenColor(token: string | undefined, fallback = PPT.text) {
  const key = (token || "").toLowerCase();
  const colors: Record<string, string> = {
    navy: PPT.navy,
    accent: PPT.accent,
    mid_gray: PPT.muted,
    light_gray: "F4F5F7",
    white: "FFFFFF",
    positive: PPT.green,
    negative: PPT.red,
    text: PPT.text,
    ink: PPT.ink,
    border: PPT.border,
  };
  if (colors[key]) return colors[key];
  return cleanHex(token, fallback);
}

function fillFor(block: PptxLayoutBlock, fallback = PPT.card) {
  return tokenColor(block.style?.fill, fallback);
}

function borderFor(block: PptxLayoutBlock, fallback = PPT.border) {
  const border = block.style?.border || "hairline_gray";
  if (border === "none") return { color: fallback, transparency: 100, width: 0 };
  if (border === "hairline_navy") return { color: PPT.navy, width: 0.75 };
  return { color: PPT.border, width: 0.75 };
}

function parseTimelineItem(text: string) {
  const bracket = text.match(/^\[([^\]]+)\]\s*(.+)$/);
  if (bracket) {
    return { date: bracket[1], body: bracket[2] };
  }
  const colon = text.match(/^([^:]{2,24}):\s*(.+)$/);
  if (colon && /\d|q[1-4]|fy|h[12]/i.test(colon[1])) {
    return { date: colon[1], body: colon[2] };
  }
  return { date: "", body: text };
}

/** First $price in string, for valuation hero treatment */
function extractLeadPrice(text: string): { hero: string; rest: string } | null {
  const t = text.replace(/\u00a0/g, " ");
  const m = t.match(/\$\s*[\d,]+(?:\.\d+)?/);
  if (!m) return null;
  const hero = m[0].replace(/\s/g, "");
  const rest = cleanText(t.replace(m[0], " ").replace(/^:\s*/, ""));
  return { hero, rest };
}

const BODY_LAYOUT_BOTTOM = 6.72;

function stretchBlueprintBodyBlocks(blocks: PptxLayoutBlock[]) {
  const drawable = blocks.filter((b) => b.type !== "cover_block" && b.type !== "comps_table");
  if (drawable.length < 2 || drawable.length > 6) return;

  const metrics = drawable.map((b) => {
    const y = Number(b.y) || 1.55;
    const h = Number(b.h) || 1.0;
    return { block: b, y, h, bottom: y + h };
  });
  const minY = Math.min(...metrics.map((m) => m.y));
  const maxBottom = Math.max(...metrics.map((m) => m.bottom));
  const span = maxBottom - minY;
  if (span < 0.55) return;
  const headroom = BODY_LAYOUT_BOTTOM - maxBottom;
  if (headroom < 0.25) return;
  if (headroom < 0.6 && drawable.length > 4) return;

  const targetBottom = BODY_LAYOUT_BOTTOM - 0.1;
  const factor = Math.min((targetBottom - minY) / span, 1.48);
  if (factor <= 1.04) return;

  for (const m of metrics) {
    const newH = Math.min(m.h * factor, BODY_LAYOUT_BOTTOM - m.y - 0.08);
    m.block.h = newH;
  }
}

function swotGroups(bullets: Bullet[]) {
  const groups: Record<"S" | "W" | "O" | "T", string[]> = {
    S: [],
    W: [],
    O: [],
    T: [],
  };

  for (const bullet of bullets) {
    const match = bullet.text.match(/^\s*([SWOT]):\s*(.+)$/i);
    if (match) {
      groups[match[1].toUpperCase() as "S" | "W" | "O" | "T"].push(match[2]);
    }
  }

  return groups;
}

function addPptHeader(pptx: any, slide: any, _sectionName: string, _slideNo?: number) {
  slide.background = { color: PPT.bg };
  slide.addShape(pptx.ShapeType.rect, {
    x: 0,
    y: 0,
    w: 0.12,
    h: PPT.h,
    line: { color: PPT.accent, transparency: 100 },
    fill: { color: PPT.accent },
  });
}

function addPptTitle(slide: any, title: string) {
  slide.addText(shortText(title, 92), {
    x: 0.55,
    y: 0.72,
    w: 8.45,
    h: 0.55,
    fontSize: 20,
    bold: true,
    color: PPT.ink,
    margin: 0,
    breakLine: false,
    fit: "shrink",
  });
}

function addPptSourceFlag(slide: any, bullet: Bullet, x: number, y: number) {
  if (!bullet.source_needed && !bullet.text.includes("(source needed)")) return;
  slide.addText("SOURCE NEEDED", {
    x,
    y,
    w: 1.25,
    h: 0.18,
    fontSize: 5.5,
    bold: true,
    color: PPT.amber,
    margin: 0,
    fit: "shrink",
  });
}

function addPptCard(
  slide: any,
  bullet: Bullet,
  index: number,
  x: number,
  y: number,
  w: number,
  h: number,
  accent = PPT.accent,
) {
  if (isDisplayNullish(bullet.text)) return;
  slide.addShape("roundRect", {
    x,
    y,
    w,
    h,
    rectRadius: 0.08,
    line: { color: PPT.border, width: 0.7 },
    fill: { color: PPT.card },
    shadow: { type: "outer", color: "CBD5E1", opacity: 0.18, blur: 1, angle: 45, distance: 1 },
  });
  slide.addShape("rect", {
    x,
    y,
    w: 0.08,
    h,
    line: { color: accent, transparency: 100 },
    fill: { color: accent },
  });
  slide.addText(String(index + 1).padStart(2, "0"), {
    x: x + 0.18,
    y: y + 0.18,
    w: 0.42,
    h: 0.22,
    fontSize: 7,
    bold: true,
    color: accent,
    margin: 0,
  });
  slide.addText(shortText(stripPrefix(bullet.text), 150), {
    x: x + 0.62,
    y: y + 0.17,
    w: w - 0.85,
    h: h - 0.25,
    fontSize: 11,
    color: PPT.text,
    margin: 0.02,
    fit: "shrink",
    valign: "mid",
    breakLine: false,
  });
  addPptSourceFlag(slide, bullet, x + w - 1.42, y + h - 0.28);
}

function addPptNotes(slide: any, notes?: string) {
  if (notes) slide.addNotes(notes);
}

function renderPptCards(slide: any, deckSlide: NormalizedSlide, accent = PPT.accent) {
  const bullets = (deckSlide.bullets || []).filter((b) => !isDisplayNullish(b.text));
  if (bullets.length === 0) return;

  const accents = [accent, PPT.green, PPT.purple, PPT.amber];
  const first = bullets[0];

  // Hero callout with accent bar
  slide.addShape("roundRect", {
    x: 0.58,
    y: 1.62,
    w: 12.15,
    h: 1.18,
    rectRadius: 0.1,
    line: { color: accent, width: 0.8 },
    fill: { color: "EFF6FF" },
  });
  slide.addShape("rect", {
    x: 0.58,
    y: 1.62,
    w: 0.1,
    h: 1.18,
    line: { color: accent, transparency: 100 },
    fill: { color: accent },
  });
  slide.addText(shortText(stripPrefix(first.text), 260), {
    x: 0.95,
    y: 1.82,
    w: 11.3,
    h: 0.72,
    fontSize: 15,
    bold: true,
    color: PPT.blue,
    margin: 0,
    fit: "shrink",
  });
  addPptSourceFlag(slide, first, 11.15, 2.48);

  // Supporting cards — cap at 4, responsive layout
  const rest = bullets.slice(1, 5);
  if (rest.length === 0) return;

  if (rest.length === 1) {
    addPptCard(slide, rest[0], 0, 0.58, 3.25, 12.15, 1.72, accents[0]);
  } else if (rest.length === 2) {
    const cw = 5.95;
    rest.forEach((bullet, i) => {
      addPptCard(slide, bullet, i, 0.58 + i * (cw + 0.25), 3.25, cw, 1.72, accents[i]);
    });
  } else if (rest.length === 3) {
    const cw = 3.88;
    const gap = (12.15 - 3 * cw) / 2;
    rest.forEach((bullet, i) => {
      addPptCard(slide, bullet, i, 0.58 + i * (cw + gap), 3.25, cw, 1.72, accents[i]);
    });
  } else {
    // 2x2 grid for 4 cards
    const cw = 5.95;
    const ch = 1.55;
    const gap = 0.25;
    rest.forEach((bullet, i) => {
      const col = i % 2;
      const row = Math.floor(i / 2);
      addPptCard(
        slide, bullet, i,
        0.58 + col * (cw + gap),
        3.25 + row * (ch + gap),
        cw, ch, accents[i],
      );
    });
  }
}

function renderPptTwoColumn(slide: any, deckSlide: NormalizedSlide) {
  const [left, right] = splitForColumns(deckSlide.bullets || []);
  const cols = [
    { title: "Market View", bullets: left, x: 0.62, accent: PPT.amber },
    { title: "Variant View", bullets: right, x: 6.92, accent: PPT.green },
  ];

  cols.forEach((col) => {
    slide.addShape("roundRect", {
      x: col.x,
      y: 1.68,
      w: 5.8,
      h: 4.72,
      rectRadius: 0.12,
      line: { color: PPT.border, width: 0.8 },
      fill: { color: PPT.card },
      shadow: { type: "outer", color: "CBD5E1", opacity: 0.16, blur: 1, angle: 45, distance: 1 },
    });
    slide.addText(col.title, {
      x: col.x + 0.3,
      y: 1.95,
      w: 5.1,
      h: 0.28,
      fontSize: 10,
      bold: true,
      color: col.accent,
      charSpace: 0.6,
      margin: 0,
    });
    col.bullets.forEach((bullet, index) => {
      slide.addText(shortText(stripPrefix(bullet.text), 130), {
        x: col.x + 0.38,
        y: 2.48 + index * 0.82,
        w: 5.02,
        h: 0.55,
        fontSize: 10.5,
        color: PPT.text,
        margin: 0,
        fit: "shrink",
      });
      slide.addShape("line", {
        x: col.x + 0.38,
        y: 3.12 + index * 0.82,
        w: 4.9,
        h: 0,
        line: { color: "E2E8F0", width: 0.5 },
      });
    });
  });
}

function renderPptTimeline(slide: any, deckSlide: NormalizedSlide) {
  const bullets = (deckSlide.bullets || []).filter((b) => !isDisplayNullish(b.text)).slice(0, 5);
  const y = 3.18;
  slide.addShape("line", {
    x: 0.9,
    y,
    w: 11.25,
    h: 0,
    line: { color: PPT.blue, width: 2.2 },
  });

  bullets.forEach((bullet, index) => {
    const item = parseTimelineItem(bullet.text);
    const x = 0.88 + index * (11.1 / Math.max(bullets.length - 1, 1));
    slide.addShape("ellipse", {
      x: x - 0.11,
      y: y - 0.11,
      w: 0.22,
      h: 0.22,
      line: { color: PPT.blue, width: 1 },
      fill: { color: PPT.accent },
    });
    slide.addText(item.date || `Step ${index + 1}`, {
      x: x - 0.72,
      y: y - 0.62,
      w: 1.42,
      h: 0.25,
      fontSize: 8,
      bold: true,
      color: PPT.blue,
      align: "center",
      margin: 0,
      fit: "shrink",
    });
    slide.addText(shortText(stripPrefix(item.body), 80), {
      x: x - 0.9,
      y: y + 0.38,
      w: 1.8,
      h: 1.15,
      fontSize: 8.4,
      color: PPT.text,
      align: "center",
      margin: 0.02,
      fit: "shrink",
    });
  });
}

function renderPptSwot(slide: any, deckSlide: NormalizedSlide) {
  const groups = swotGroups(deckSlide.bullets || []);
  const title = deckSlide.title.toLowerCase();
  const external = title.includes("opportunit") || title.includes("threat");
  const cells = external
    ? [
        { key: "O" as const, title: "Opportunities", x: 0.55, color: PPT.blue },
        { key: "T" as const, title: "Threats", x: 6.78, color: PPT.red },
      ]
    : [
        { key: "S" as const, title: "Strengths", x: 0.55, color: PPT.green },
        { key: "W" as const, title: "Weaknesses", x: 6.78, color: PPT.red },
      ];
  const cw = 6.05;
  const ch = 4.88;
  const y0 = 1.52;

  cells.forEach((cell) => {
    slide.addShape("roundRect", {
      x: cell.x,
      y: y0,
      w: cw,
      h: ch,
      rectRadius: 0.1,
      line: { color: PPT.border, width: 0.8 },
      fill: { color: PPT.card },
    });
    slide.addShape("rect", {
      x: cell.x,
      y: y0,
      w: 0.1,
      h: ch,
      line: { color: cell.color, transparency: 100 },
      fill: { color: cell.color },
    });
    slide.addText(cell.title, {
      x: cell.x + 0.32,
      y: y0 + 0.22,
      w: cw - 0.55,
      h: 0.32,
      fontSize: 11,
      bold: true,
      color: cell.color,
      margin: 0,
    });
    const items = groups[cell.key].filter((t) => !isDisplayNullish(t));
    const bodyLines = items.length
      ? items.slice(0, 4)
      : (deckSlide.bullets || []).slice(0, 2).map((b) => stripPrefix(b.text)).filter((t) => !isDisplayNullish(t));

    slide.addText(
      bodyLines.map((text) => ({ text: shortText(text, 120), options: { breakLine: true } })),
      {
        x: cell.x + 0.32,
        y: y0 + 0.68,
        w: cw - 0.5,
        h: ch - 0.9,
        fontSize: 10,
        color: PPT.text,
        bullet: { type: "ul" },
        fit: "shrink",
        margin: 0,
      },
    );
  });
}

function renderPptPriceTargetBridge(slide: any, deckSlide: NormalizedSlide) {
  const lines = (deckSlide.bullets || [])
    .map((b) => stripPrefix(b.text))
    .filter((t) => !isDisplayNullish(t));
  if (!lines.length) return;

  let heroLine = "";
  let heroDollar: string | null = null;
  let heroRest = "";
  for (const line of lines) {
    const parsed = extractLeadPrice(line);
    if (parsed) {
      heroLine = line;
      heroDollar = parsed.hero;
      heroRest = parsed.rest;
      break;
    }
  }

  const leftX = 0.55;
  const leftW = 6.05;
  const topY = 1.48;
  const hMain = 4.92;

  slide.addShape("roundRect", {
    x: leftX,
    y: topY,
    w: leftW,
    h: hMain,
    rectRadius: 0.14,
    line: { color: "BFDBFE", width: 0.85 },
    fill: { color: "EFF6FF" },
  });
  slide.addShape("rect", {
    x: leftX,
    y: topY,
    w: 0.11,
    h: hMain,
    line: { color: PPT.accent, transparency: 100 },
    fill: { color: PPT.accent },
  });

  if (heroDollar) {
    const isDcf = /dcf|discounted cash flow/i.test(heroLine);
    slide.addText((isDcf ? "DCF target" : "Price target").toUpperCase(), {
      x: leftX + 0.38,
      y: topY + 0.32,
      w: leftW - 0.65,
      h: 0.24,
      fontSize: 8,
      bold: true,
      color: PPT.blue,
      margin: 0,
      charSpace: 0.8,
    });
    slide.addText(heroDollar, {
      x: leftX + 0.34,
      y: topY + 0.62,
      w: leftW - 0.65,
      h: 1.05,
      fontSize: 32,
      bold: true,
      color: PPT.ink,
      margin: 0,
      fit: "shrink",
    });
    const sub = heroRest || cleanText(heroLine.replace(/\$\s*[\d,]+(?:\.\d+)?/, "")) || lines[0];
    slide.addText(shortText(sub, 240), {
      x: leftX + 0.34,
      y: topY + 1.85,
      w: leftW - 0.6,
      h: hMain - 2.15,
      fontSize: 11.5,
      color: PPT.text,
      margin: 0,
      fit: "shrink",
    });
  } else {
    slide.addText(shortText(lines[0], 280), {
      x: leftX + 0.34,
      y: topY + 0.42,
      w: leftW - 0.6,
      h: hMain - 0.7,
      fontSize: 15,
      bold: true,
      color: PPT.ink,
      margin: 0,
      fit: "shrink",
    });
  }

  const rightX = leftX + leftW + 0.35;
  const rightW = 6.05;
  const support = lines.filter((ln) => ln !== heroLine);
  if (!support.length) return;

  slide.addText("Methodology context", {
    x: rightX,
    y: topY + 0.22,
    w: rightW,
    h: 0.26,
    fontSize: 9,
    bold: true,
    color: PPT.muted,
    margin: 0,
  });

  let yOff = topY + 0.52;
  for (const line of support.slice(0, 4)) {
    slide.addShape("roundRect", {
      x: rightX,
      y: yOff,
      w: rightW,
      h: 1.05,
      rectRadius: 0.08,
      line: { color: PPT.border, width: 0.6 },
      fill: { color: PPT.card },
    });
    slide.addText(shortText(line, 200), {
      x: rightX + 0.22,
      y: yOff + 0.18,
      w: rightW - 0.44,
      h: 0.78,
      fontSize: 10,
      color: PPT.text,
      margin: 0.02,
      fit: "shrink",
    });
    yOff += 1.15;
  }
}

function renderPptValuation(slide: any, deckSlide: NormalizedSlide) {
  const bullets = (deckSlide.bullets || []).filter((b) => !isDisplayNullish(b.text));
  const main = bullets[0];
  if (main) {
    slide.addShape("roundRect", {
      x: 0.65,
      y: 1.58,
      w: 5.25,
      h: 4.7,
      rectRadius: 0.12,
      line: { color: "BFDBFE", width: 0.8 },
      fill: { color: "EFF6FF" },
    });
    slide.addText("Valuation Takeaway", {
      x: 1.02,
      y: 1.92,
      w: 4.4,
      h: 0.25,
      fontSize: 9,
      bold: true,
      color: PPT.blue,
      margin: 0,
    });
    slide.addText(shortText(stripPrefix(main.text), 260), {
      x: 1.02,
      y: 2.35,
      w: 4.35,
      h: 2.45,
      fontSize: 15,
      bold: true,
      color: PPT.ink,
      margin: 0,
      fit: "shrink",
    });
  }

  bullets.slice(1, 4).forEach((bullet, index) => {
    addPptCard(slide, bullet, index, 6.35, 1.62 + index * 1.42, 6.35, 1.15, [
      PPT.green,
      PPT.blue,
      PPT.purple,
    ][index]);
  });
}

function addPptCompsTable(slide: any, block: Pick<PptxLayoutBlock, "x" | "y" | "w" | "h" | "highlight_row_index">, compsData: any) {
  const headers = compsData?.headers || [];
  const rows = compsData?.rows || [];
  if (!headers.length || !rows.length) return false;

  const highlightIdx = block.highlight_row_index ?? compsData.subject_index ?? 0;
  const tableRows: any[][] = [
    headers.map((header: string, colIdx: number) => ({
      text: header,
      options: {
        bold: true,
        fontSize: colIdx === 0 ? 7 : 6.4,
        color: PPT.muted,
        fill: { color: "F1F5F9" },
        border: [null, null, { pt: 0.5, color: PPT.border }, null],
        align: (colIdx === 0 ? "left" : "right") as any,
        valign: "middle" as const,
      },
    })),
  ];

  rows.forEach((row: any[], rowIdx: number) => {
    const isHighlight = rowIdx === highlightIdx;
    tableRows.push(
      row.map((cell: any, colIdx: number) => {
        let val = cell;
        if (val === null || val === undefined) val = "-";
        else if (typeof val === "number") {
          if (colIdx >= 2 && colIdx <= 3) val = val >= 1e12 ? `${(val / 1e12).toFixed(1)}T` : val >= 1e9 ? `${(val / 1e9).toFixed(1)}B` : val >= 1e6 ? `${(val / 1e6).toFixed(1)}M` : val.toLocaleString();
          else if (colIdx >= 9) val = `${(val * 100).toFixed(1)}%`;
          else if (colIdx === 1) val = val.toFixed(2);
          else val = val.toFixed(2);
        }
        return {
          text: String(val),
          options: {
            fontSize: colIdx === 0 ? 7.1 : 6.6,
            color: isHighlight ? PPT.accent : PPT.ink,
            bold: isHighlight,
            fill: { color: isHighlight ? "EFF6FF" : rowIdx % 2 === 0 ? "FFFFFF" : "F8FAFC" },
            border: [null, null, { pt: 0.3, color: "E2E8F0" }, null],
            align: (colIdx === 0 ? "left" : "right") as any,
            valign: "middle" as const,
          },
        };
      }),
    );
  });

  const { x, y, w } = blockBounds(block as PptxLayoutBlock);
  slide.addTable(tableRows, {
    x,
    y,
    w,
    colW: headers.map((_: string, i: number) => (i === 0 ? 1.1 : (w - 1.1) / Math.max(headers.length - 1, 1))),
    rowH: 0.34,
    margin: [2, 3, 2, 3],
  });
  return true;
}

function renderPptBlueprint(slide: any, deckSlide: NormalizedSlide, design: PptxSlideDesign, compsData?: any) {
  const blocks = design.blocks || [];
  if (blocks.length === 0) return false;

  stretchBlueprintBodyBlocks(blocks);

  blocks.forEach((block, index) => {
    // Skip cover_block (title slide is rendered separately)
    if (block.type === "cover_block") return;

    // Comps table: render as PptxGenJS table from deck comps data
    if (block.type === "comps_table" && compsData) {
      addPptCompsTable(slide, block, compsData);
      return;
    }

    const { x, y, w, h } = blockBounds(block);
    const accent = cleanHex(block.accent_color || design.accent_color, PPT.accent);
    const refTexts = resolveTextRefs(deckSlide, block.text_refs);
    const staticText = (block.static_text || []).filter(Boolean);
    const text = block.body
      ? shortText(block.body, 220)
      : block.type === "bullet_card" && refTexts.length > 1
        ? refTexts.map((item) => `- ${shortText(item, 120)}`).join("\n")
        : shortText(refTexts.join(" / ") || sourceText(deckSlide, block.text_source), 220);

    const skipIfEmpty = new Set([
      "hero_callout",
      "bullet_card",
      "metric_tile",
      "timeline_item",
      "risk_box",
      "valuation_callout",
      "text_box",
    ]);
    if (skipIfEmpty.has(block.type) && isDisplayNullish(text)) return;
    if (block.type === "two_column_panel" && refTexts.length === 0) return;

    const label = shortText(block.label || block.title || staticText[0] || "", 64);
    const textColor = tokenColor(block.style?.text_color, PPT.text);
    const headerColor = tokenColor(block.style?.header_color, accent);
    const align = block.style?.alignment || "left";

    // Tone-aware accent bar color
    const toneAccent = block.tone === "positive" ? PPT.green
      : block.tone === "negative" ? PPT.red
      : block.tone === "accent" ? accent
      : accent;

    if (block.type === "hero_callout" || block.type === "valuation_callout") {
      const isValuationHero = block.type === "valuation_callout";
      const priceParsed = isValuationHero ? extractLeadPrice(text) : null;

      slide.addShape("roundRect", {
        x,
        y,
        w,
        h,
        rectRadius: 0.12,
        line: borderFor(block, toneAccent),
        fill: { color: fillFor(block, isValuationHero ? "EFF6FF" : PPT.card) },
        shadow: { type: "outer", color: "CBD5E1", opacity: 0.18, blur: 1, angle: 45, distance: 1 },
      });
      slide.addShape("rect", {
        x,
        y,
        w: 0.1,
        h,
        line: { color: toneAccent, transparency: 100 },
        fill: { color: toneAccent },
      });
      if (label) {
        slide.addText(label.toUpperCase(), {
          x: x + 0.32,
          y: y + 0.18,
          w: w - 0.55,
          h: 0.22,
          fontSize: 7,
          bold: true,
          color: headerColor,
          margin: 0,
          charSpace: 0.8,
          align,
        });
      }

      if (priceParsed?.hero) {
        slide.addText(priceParsed.hero, {
          x: x + 0.32,
          y: y + (label ? 0.48 : 0.26),
          w: w - 0.55,
          h: 0.95,
          fontSize: 28,
          bold: true,
          color: PPT.ink,
          margin: 0,
          fit: "shrink",
          valign: "mid",
          align,
        });
        const sub = priceParsed.rest ? shortText(priceParsed.rest, 180) : "";
        if (sub && !isDisplayNullish(sub)) {
          slide.addText(sub, {
            x: x + 0.32,
            y: y + h - 1.35,
            w: w - 0.55,
            h: 1.05,
            fontSize: 11,
            bold: false,
            color: textColor,
            margin: 0,
            fit: "shrink",
            valign: "mid",
            align,
          });
        }
      } else {
        slide.addText(text, {
          x: x + 0.32,
          y: y + (label ? 0.5 : 0.22),
          w: w - 0.55,
          h: h - (label ? 0.65 : 0.35),
          fontSize: block.type === "valuation_callout" ? 15 : 14,
          bold: true,
          color: block.style?.fill === "navy" || block.style?.fill === "accent" ? "FFFFFF" : PPT.ink,
          margin: 0,
          fit: "shrink",
          valign: "mid",
          align,
        });
      }
      return;
    }

    if (block.type === "metric_tile") {
      slide.addShape("roundRect", {
        x,
        y,
        w,
        h,
        rectRadius: 0.1,
        line: borderFor(block, accent),
        fill: { color: fillFor(block, "F8FAFC") },
      });
      slide.addText(label || `KPI ${index + 1}`, {
        x: x + 0.18,
        y: y + 0.14,
        w: w - 0.36,
        h: 0.22,
        fontSize: 6.8,
        bold: true,
        color: headerColor,
        margin: 0,
        fit: "shrink",
        align,
      });
      slide.addText(text, {
        x: x + 0.18,
        y: y + 0.42,
        w: w - 0.36,
        h: h - 0.52,
        fontSize: 10.5,
        bold: true,
        color: textColor,
        margin: 0,
        fit: "shrink",
        align,
      });
      return;
    }

    if (block.type === "timeline_item") {
      const parsed = parseTimelineItem(text);
      const timelineLabel = label || parsed.date || `Step ${index + 1}`;
      const timelineBody = parsed.date && !label ? parsed.body : text;
      slide.addShape("ellipse", {
        x,
        y,
        w: 0.18,
        h: 0.18,
        line: { color: accent, width: 1 },
        fill: { color: accent },
      });
      slide.addText(timelineLabel, {
        x: x + 0.28,
        y: y - 0.04,
        w: w - 0.28,
        h: 0.24,
        fontSize: 8,
        bold: true,
        color: headerColor,
        margin: 0,
        fit: "shrink",
        align,
      });
      slide.addText(timelineBody, {
        x: x + 0.28,
        y: y + 0.28,
        w: w - 0.28,
        h: h - 0.26,
        fontSize: 8.4,
        color: textColor,
        margin: 0,
        fit: "shrink",
        align,
      });
      return;
    }

    const isRisk = block.type === "risk_box";
    const isPanel = block.type === "two_column_panel";
    const severityColor = block.severity === "high" ? PPT.red
      : block.severity === "medium" ? PPT.amber
      : block.severity === "low" ? PPT.amber
      : isRisk ? PPT.red : PPT.border;
    const fill = fillFor(block, isRisk ? "FEF2F2" : isPanel ? "F8FAFC" : PPT.card);

    if (isPanel) {
      const midpoint = Math.ceil(refTexts.length / 2);
      const leftTexts = refTexts.slice(0, midpoint);
      const rightTexts = refTexts.slice(midpoint);
      const leftHeading = staticText[0] || label || "View 1";
      const rightHeading = staticText[1] || block.title || "View 2";
      const colGap = 0.22;
      const colW = (w - colGap) / 2;
      const leftAccent = block.tone === "negative" ? PPT.red : block.tone === "positive" ? PPT.green : toneAccent;
      const rightAccent = block.tone === "positive" ? PPT.red : block.tone === "negative" ? PPT.green : PPT.navy;

      [
        { heading: leftHeading, texts: leftTexts, x: x, accent: leftAccent },
        { heading: rightHeading, texts: rightTexts.length ? rightTexts : leftTexts.slice(1), x: x + colW + colGap, accent: rightAccent },
      ].forEach((column) => {
        slide.addShape("roundRect", {
          x: column.x,
          y,
          w: colW,
          h,
          rectRadius: 0.08,
          line: { color: PPT.border, width: 0.75 },
          fill: { color: fill },
          shadow: { type: "outer", color: "CBD5E1", opacity: 0.1, blur: 1, angle: 45, distance: 1 },
        });
        slide.addShape("rect", {
          x: column.x,
          y,
          w: 0.08,
          h,
          line: { color: column.accent, transparency: 100 },
          fill: { color: column.accent },
        });
        slide.addText(column.heading, {
          x: column.x + 0.22,
          y: y + 0.16,
          w: colW - 0.44,
          h: 0.26,
          fontSize: 8.5,
          bold: true,
          color: column.accent,
          margin: 0,
          fit: "shrink",
          align,
        });
        slide.addText(column.texts.map((item) => `- ${shortText(item, 130)}`).join("\n"), {
          x: column.x + 0.22,
          y: y + 0.54,
          w: colW - 0.44,
          h: h - 0.72,
          fontSize: 9.1,
          color: textColor,
          breakLine: false,
          fit: "shrink",
          margin: 0.02,
          valign: "mid",
          align,
        });
      });
      return;
    }

    slide.addShape("roundRect", {
      x,
      y,
      w,
      h,
      rectRadius: 0.08,
      line: borderFor(block, severityColor),
      fill: { color: fill },
      shadow: { type: "outer", color: "CBD5E1", opacity: 0.12, blur: 1, angle: 45, distance: 1 },
    });
    if (label) {
      slide.addText(label, {
        x: x + 0.22,
        y: y + 0.16,
        w: w - 0.44,
        h: 0.24,
        fontSize: 8,
        bold: true,
        color: isRisk ? PPT.red : headerColor,
        margin: 0,
        fit: "shrink",
        align,
      });
    }
    slide.addText(text, {
      x: x + 0.22,
      y: y + (label ? 0.48 : 0.2),
      w: w - 0.44,
      h: h - (label ? 0.62 : 0.34),
      fontSize: block.type === "section_badge" ? 12 : 9.8,
      bold: block.type === "section_badge",
      color: textColor,
      margin: 0.02,
      fit: "shrink",
      valign: "mid",
      align,
    });
  });

  return true;
}

function renderPptSlide(
  pptx: any,
  pptSlide: any,
  section: NormalizedSection,
  slide: NormalizedSlide,
  slideNo: number,
  design?: PptxSlideDesign,
  generatedDate?: string,
  compsData?: any,
) {
  addPptHeader(pptx, pptSlide, toTitleCase(section.section_id), slideNo);
  addPptTitle(pptSlide, slide.title);

  const kind = design?.layout || slideKind(section, slide);
  const accent = cleanHex(design?.accent_color, PPT.accent);
  const isCompsSlide = /comparable|comparables/i.test(section.section_id) || /comparable|comp\b/i.test(slide.title);
  const renderedCompsTable = Boolean(
    isCompsSlide && compsData && addPptCompsTable(
      pptSlide,
      { x: 0.55, y: 1.45, w: 12.25, h: 4.9, highlight_row_index: 0 },
      compsData,
    ),
  );
  if (renderedCompsTable) {
    pptSlide.addText("Source: computed market data at deck generation time.", {
      x: 0.55,
      y: 6.5,
      w: 6.2,
      h: 0.18,
      fontSize: 6.5,
      italic: true,
      color: PPT.muted,
      margin: 0,
    });
  }
  const sectionLower = section.section_id.toLowerCase();
  const titleLower = slide.title.toLowerCase();
  const swotPreferred =
    sectionLower.includes("swot") && (slide.bullets || []).some((b) => /^\s*[SWOT]:/i.test(b.text));
  const timelinePreferred =
    slide.layout_hints?.suggested_visual === "timeline"
    || /catalyst.*timeline|timeline/i.test(`${sectionLower} ${titleLower}`);
  const priceBridgePreferred = /price target bridge/i.test(titleLower);

  let usedDedicatedLayout = false;
  if (!renderedCompsTable && swotPreferred) {
    renderPptSwot(pptSlide, slide);
    usedDedicatedLayout = true;
  } else if (!renderedCompsTable && timelinePreferred) {
    renderPptTimeline(pptSlide, slide);
    usedDedicatedLayout = true;
  } else if (!renderedCompsTable && priceBridgePreferred) {
    renderPptPriceTargetBridge(pptSlide, slide);
    usedDedicatedLayout = true;
  }

  const renderedBlueprint = !renderedCompsTable && !usedDedicatedLayout && Boolean(
    design?.blocks?.length && renderPptBlueprint(pptSlide, slide, design, compsData),
  );
  if (!renderedCompsTable && !usedDedicatedLayout && !renderedBlueprint) {
    if (kind === "timeline") renderPptTimeline(pptSlide, slide);
    else if (kind === "swot") renderPptSwot(pptSlide, slide);
    else if (kind === "two_column") renderPptTwoColumn(pptSlide, slide);
    else if (kind === "valuation") renderPptValuation(pptSlide, slide);
    else renderPptCards(pptSlide, slide, accent);
  }

  // Footer: branding (left), date (center), slide number (right)
  pptSlide.addText("TickerStats", {
    x: 0.58,
    y: 7.02,
    w: 1.5,
    h: 0.18,
    fontSize: 6.5,
    color: PPT.muted,
    margin: 0,
  });
  if (generatedDate) {
    pptSlide.addText(generatedDate, {
      x: 5.4,
      y: 7.02,
      w: 2.5,
      h: 0.18,
      fontSize: 6.5,
      color: PPT.muted,
      margin: 0,
      align: "center",
    });
  }
  pptSlide.addText(String(slideNo).padStart(2, "0"), {
    x: 11.5,
    y: 7.02,
    w: 1.25,
    h: 0.18,
    fontSize: 6.5,
    color: PPT.muted,
    margin: 0,
    align: "right",
  });
  addPptNotes(pptSlide, slide.speaker_notes);
}

function pdfSet(doc: any, color: [number, number, number]) {
  doc.setTextColor(color[0], color[1], color[2]);
}

function pdfFill(doc: any, color: [number, number, number]) {
  doc.setFillColor(color[0], color[1], color[2]);
}

function pdfSourceFlag(doc: any, bullet: Bullet, x: number, y: number) {
  if (!bullet.source_needed && !bullet.text.includes("(source needed)")) return;
  pdfSet(doc, [217, 119, 6]);
  doc.setFontSize(5.5);
  doc.text("SOURCE NEEDED", x, y);
}

function pdfSectionDivider(
  doc: any,
  pageW: number,
  pageH: number,
  sectionName: string,
  slideCount: number,
) {
  pdfFill(doc, PDF.navy);
  doc.rect(0, 0, pageW, pageH, "F");
  pdfFill(doc, PDF.accent);
  doc.rect(0, 0, 5, pageH, "F");
  pdfSet(doc, [186, 230, 253]);
  doc.setFontSize(8);
  doc.text("SECTION", 22, pageH / 2 - 22);
  pdfSet(doc, [255, 255, 255]);
  doc.setFontSize(28);
  doc.text(sectionName, 22, pageH / 2 - 6);
  pdfFill(doc, PDF.accent);
  doc.rect(22, pageH / 2 + 2, 20, 1.2, "F");
  pdfSet(doc, [148, 163, 184]);
  doc.setFontSize(9);
  doc.text(`${slideCount} slide${slideCount !== 1 ? "s" : ""}`, 22, pageH / 2 + 14);
}

function pdfDrawShell(doc: any, pageW: number, pageH: number, sectionId: string, title: string) {
  pdfFill(doc, PDF.bg);
  doc.rect(0, 0, pageW, pageH, "F");
  pdfFill(doc, PDF.navy);
  doc.rect(0, 0, pageW, 10, "F");
  pdfSet(doc, [224, 242, 254]);
  doc.setFontSize(7);
  doc.text(toTitleCase(sectionId).toUpperCase(), 14, 6.8);
  pdfSet(doc, PDF.ink);
  doc.setFontSize(20);
  doc.text(shortText(title, 120), 14, 26);
  pdfFill(doc, PDF.accent);
  doc.rect(14, 31, 16, 1.4, "F");
}

function pdfCard(
  doc: any,
  text: string,
  x: number,
  y: number,
  w: number,
  h: number,
  options: {
    fontSize?: number;
    accentColor?: [number, number, number];
    index?: number;
    bullet?: Bullet;
  } = {},
) {
  const fontSize = options.fontSize || 10.5;
  const accentColor = options.accentColor;

  // Card background
  pdfFill(doc, PDF.card);
  doc.setDrawColor(...PDF.border);
  doc.roundedRect(x, y, w, h, 2, 2, "FD");

  // Accent bar on left
  if (accentColor) {
    pdfFill(doc, accentColor);
    doc.rect(x, y, 2.5, h, "F");
  }

  const textX = accentColor ? x + 6 : x + 4;
  const textW = accentColor ? w - 10 : w - 8;

  // Card number
  if (options.index !== undefined && accentColor) {
    pdfSet(doc, accentColor);
    doc.setFontSize(7);
    doc.text(String(options.index + 1).padStart(2, "0"), textX, y + 6);
  }

  // Card text with height-aware clipping
  pdfSet(doc, PDF.text);
  doc.setFontSize(fontSize);
  const maxLines = Math.max(1, Math.floor((h - 12) / (fontSize * 0.42)));
  const cleaned = text ? shortText(stripPrefix(text), 240) : "";
  if (cleaned) {
    const lines = doc.splitTextToSize(cleaned, textW);
    doc.text(lines.slice(0, maxLines), textX, y + (options.index !== undefined ? 12 : 8));
  }

  // Source flag
  if (options.bullet) {
    pdfSourceFlag(doc, options.bullet, x + w - 28, y + h - 5);
  }
}

function renderPdfCards(doc: any, slide: NormalizedSlide) {
  const bullets = slide.bullets || [];
  const pdfAccents: [number, number, number][] = [
    PDF.accent, [22, 163, 74], [124, 58, 237], [217, 119, 6],
  ];

  if (bullets[0]) {
    // Hero callout with accent bar
    pdfFill(doc, [239, 246, 255]);
    doc.setDrawColor(191, 219, 254);
    doc.roundedRect(14, 39, 269, 27, 2, 2, "FD");
    pdfFill(doc, PDF.accent);
    doc.rect(14, 39, 2.5, 27, "F");
    pdfSet(doc, PDF.blue);
    doc.setFontSize(13);
    const heroLines = doc.splitTextToSize(shortText(stripPrefix(bullets[0].text), 280), 248);
    doc.text(heroLines.slice(0, 4), 22, 50);
    pdfSourceFlag(doc, bullets[0], 252, 62);
  }

  // Supporting cards — cap at 4, responsive layout
  const rest = bullets.slice(1, 5);
  if (rest.length === 0) return;

  if (rest.length <= 3) {
    const cw = rest.length === 1 ? 269 : rest.length === 2 ? 131 : 86;
    const gap = rest.length === 1 ? 0 : rest.length === 2 ? 7 : 5.5;
    rest.forEach((bullet, i) => {
      pdfCard(doc, bullet.text, 14 + i * (cw + gap), 80, cw, 46, {
        accentColor: pdfAccents[i % 4],
        index: i,
        bullet,
      });
    });
  } else {
    // 2x2 grid for 4 cards
    const cw = 131;
    const ch = 38;
    const gapX = 7;
    const gapY = 5;
    rest.forEach((bullet, i) => {
      const col = i % 2;
      const row = Math.floor(i / 2);
      pdfCard(doc, bullet.text, 14 + col * (cw + gapX), 80 + row * (ch + gapY), cw, ch, {
        accentColor: pdfAccents[i % 4],
        index: i,
        bullet,
      });
    });
  }
}

function renderPdfTwoColumn(doc: any, slide: NormalizedSlide) {
  const [left, right] = splitForColumns(slide.bullets || []);
  const colColors: [number, number, number][] = [[217, 119, 6], [22, 163, 74]];
  [
    { title: "Market View", bullets: left, x: 14, accent: colColors[0] },
    { title: "Variant View", bullets: right, x: 151, accent: colColors[1] },
  ].forEach((col) => {
    pdfCard(doc, "", col.x, 39, 132, 95);
    pdfFill(doc, col.accent);
    doc.rect(col.x, 39, 2.5, 95, "F");
    pdfSet(doc, col.accent);
    doc.setFontSize(10);
    doc.text(col.title.toUpperCase(), col.x + 7, 48);
    pdfSet(doc, PDF.text);
    doc.setFontSize(9.3);
    let y = 58;
    for (const bullet of col.bullets) {
      const lines = doc.splitTextToSize(shortText(stripPrefix(bullet.text), 140), 116);
      doc.text(lines.slice(0, 3), col.x + 7, y);
      y += 18;
    }
  });
}

function renderPdfTimeline(doc: any, slide: NormalizedSlide) {
  const bullets = (slide.bullets || []).slice(0, 5);
  doc.setDrawColor(...PDF.blue);
  doc.setLineWidth(1.2);
  doc.line(24, 82, 274, 82);
  bullets.forEach((bullet, index) => {
    const item = parseTimelineItem(bullet.text);
    const x = 24 + index * (250 / Math.max(bullets.length - 1, 1));
    pdfFill(doc, PDF.accent);
    doc.circle(x, 82, 2.7, "F");
    pdfSet(doc, PDF.blue);
    doc.setFontSize(8);
    doc.text(item.date || `Step ${index + 1}`, x, 69, { align: "center" });
    pdfSet(doc, PDF.text);
    doc.setFontSize(7.5);
    const lines = doc.splitTextToSize(shortText(stripPrefix(item.body), 80), 45);
    doc.text(lines.slice(0, 5), x, 94, { align: "center" });
  });
}

function renderPdfSwot(doc: any, slide: NormalizedSlide) {
  const groups = swotGroups(slide.bullets || []);
  const swotColors: Record<string, [number, number, number]> = {
    S: [22, 163, 74],
    W: [217, 119, 6],
    O: [30, 58, 138],
    T: [220, 38, 38],
  };
  const cells = [
    { key: "S" as const, title: "Strengths", x: 14, y: 39 },
    { key: "W" as const, title: "Weaknesses", x: 151, y: 39 },
    { key: "O" as const, title: "Opportunities", x: 14, y: 101 },
    { key: "T" as const, title: "Threats", x: 151, y: 101 },
  ];
  cells.forEach((cell) => {
    pdfCard(doc, "", cell.x, cell.y, 132, 49);
    pdfFill(doc, swotColors[cell.key]);
    doc.rect(cell.x, cell.y, 2.5, 49, "F");
    pdfSet(doc, swotColors[cell.key]);
    doc.setFontSize(10);
    doc.text(cell.title, cell.x + 7, cell.y + 10);
    pdfSet(doc, PDF.text);
    doc.setFontSize(8.8);
    const items = groups[cell.key].length
      ? groups[cell.key]
      : (slide.bullets || []).slice(0, 2).map((b) => stripPrefix(b.text));
    const lines = items.slice(0, 2).flatMap((item) =>
      doc.splitTextToSize(`\u2022 ${shortText(item, 90)}`, 116),
    );
    doc.text(lines.slice(0, 5), cell.x + 7, cell.y + 22);
  });
}

function renderPdfValuation(doc: any, slide: NormalizedSlide) {
  const bullets = slide.bullets || [];
  if (bullets[0]) {
    pdfCard(doc, "", 14, 39, 120, 95);
    pdfFill(doc, PDF.accent);
    doc.rect(14, 39, 2.5, 95, "F");
    pdfSet(doc, PDF.blue);
    doc.setFontSize(9);
    doc.text("VALUATION TAKEAWAY", 22, 48);
    pdfSet(doc, PDF.ink);
    doc.setFontSize(13);
    const valLines = doc.splitTextToSize(shortText(stripPrefix(bullets[0].text), 260), 102);
    doc.text(valLines.slice(0, 8), 22, 60);
    pdfSourceFlag(doc, bullets[0], 100, 128);
  }
  bullets.slice(1, 4).forEach((bullet, index) => {
    pdfCard(doc, bullet.text, 150, 39 + index * 33, 133, 26, {
      fontSize: 9.5,
      accentColor: [[22, 163, 74], PDF.blue, [124, 58, 237]][index] as [number, number, number],
      index,
      bullet,
    });
  });
}

function renderPdfSlide(doc: any, section: NormalizedSection, slide: NormalizedSlide) {
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  pdfDrawShell(doc, pageW, pageH, section.section_id, slide.title);

  const kind = slideKind(section, slide);
  if (kind === "timeline") renderPdfTimeline(doc, slide);
  else if (kind === "swot") renderPdfSwot(doc, slide);
  else if (kind === "two_column") renderPdfTwoColumn(doc, slide);
  else if (kind === "valuation") renderPdfValuation(doc, slide);
  else renderPdfCards(doc, slide);
}

// ---------------------------------------------------------------------------
// PDF export
// ---------------------------------------------------------------------------

export async function exportDeckToPDF(
  data: DeckExportData,
  filename: string,
) {
  const { jsPDF } = await import("jspdf");

  const doc = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();

  const sections = normalizeSections(data);
  const { ticker, companyName } = getDeckTitle(data);
  const genDate = getGeneratedDate(data);
  const dateStr = formatDate(genDate);
  const { sectionCount, slideCount } = countSlidesAndSections(sections);

  // ---------- Title slide ----------
  pdfFill(doc, PDF.navy);
  doc.rect(0, 0, pageW, pageH, "F");
  pdfFill(doc, PDF.accent);
  doc.rect(0, 0, 7, pageH, "F");

  // Company name and subtitle
  pdfSet(doc, [186, 230, 253]);
  doc.setFontSize(9);
  doc.text("INVESTMENT PITCH DECK", 28, pageH / 2 - 30);
  pdfSet(doc, [255, 255, 255]);
  doc.setFontSize(34);
  doc.text(companyName, 28, pageH / 2 - 14);
  pdfFill(doc, PDF.accent);
  doc.rect(28, pageH / 2 - 8, 20, 1.2, "F");
  pdfSet(doc, [224, 242, 254]);
  doc.setFontSize(16);
  doc.text(ticker, 28, pageH / 2 + 4);

  // Right info panel
  pdfFill(doc, [30, 41, 59]);
  doc.roundedRect(190, pageH / 2 - 38, 84, 76, 3, 3, "F");
  pdfSet(doc, [186, 230, 253]);
  doc.setFontSize(9);
  doc.text("Generated by TickerStats", 198, pageH / 2 - 26);
  pdfSet(doc, [255, 255, 255]);
  doc.setFontSize(12);
  doc.text("Research output for", 198, pageH / 2 - 14);
  doc.text("investment committee review", 198, pageH / 2 - 6);
  pdfSet(doc, [203, 213, 225]);
  doc.setFontSize(8);
  if (dateStr) {
    doc.text(`Generated: ${dateStr}`, 198, pageH / 2 + 10);
  }
  doc.text(
    `${sectionCount} section${sectionCount !== 1 ? "s" : ""} \u00b7 ${slideCount} slide${slideCount !== 1 ? "s" : ""}`,
    198,
    pageH / 2 + 20,
  );

  // ---------- Section slides ----------
  for (const section of sections) {
    // Section divider page
    doc.addPage();
    pdfSectionDivider(
      doc,
      pageW,
      pageH,
      toTitleCase(section.section_id),
      (section.slides || []).length,
    );

    for (const slide of section.slides || []) {
      doc.addPage();
      renderPdfSlide(doc, section, slide);
    }
  }

  // ---------- Final-pass footer on all pages after title ----------
  const totalPages = doc.getNumberOfPages();
  for (let i = 2; i <= totalPages; i++) {
    doc.setPage(i);
    // Footer separator line
    doc.setDrawColor(...PDF.border);
    doc.setLineWidth(0.3);
    doc.line(14, pageH - 14, pageW - 14, pageH - 14);
    // Left: branding
    pdfSet(doc, PDF.muted);
    doc.setFontSize(7);
    doc.text("TickerStats", 14, pageH - 8);
    // Center: date
    if (dateStr) {
      doc.text(dateStr, pageW / 2, pageH - 8, { align: "center" as any });
    }
    // Right: page number
    doc.text(`${i - 1} / ${totalPages - 1}`, pageW - 14, pageH - 8, { align: "right" as any });
  }

  doc.save(filename);
}

// ---------------------------------------------------------------------------
// PPTX export
// ---------------------------------------------------------------------------

export async function exportDeckToPPTX(
  data: DeckExportData,
  filename: string,
  options: { designSpec?: PptxDesignSpec } = {},
) {
  const PptxGenJS = (await import("pptxgenjs")).default;
  PPT = mergePptTheme(options.designSpec);

  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 inches
  pptx.author = "TickerStats";
  pptx.subject = "Investment pitch deck";
  pptx.theme = {
    headFontFace: options.designSpec?.theme?.head_font_face || "Aptos Display",
    bodyFontFace: options.designSpec?.theme?.body_font_face || "Aptos",
  };

  const sections = normalizeSections(data);
  const { ticker, companyName } = getDeckTitle(data);

  // ---------- Title slide ----------
  const titleSlide = pptx.addSlide();
  titleSlide.background = { color: PPT.navy };
  titleSlide.addShape(pptx.ShapeType.rect, {
    x: 0,
    y: 0,
    w: 0.22,
    h: PPT.h,
    line: { color: PPT.accent, transparency: 100 },
    fill: { color: PPT.accent },
  });
  titleSlide.addText("INVESTMENT PITCH DECK", {
    x: 0.72,
    y: 1.52,
    w: 4.8,
    h: 0.28,
    fontSize: 8,
    bold: true,
    color: "BAE6FD",
    margin: 0,
  });
  titleSlide.addText(companyName, {
    x: 0.72,
    y: 2.12,
    w: 8.8,
    h: 0.9,
    fontSize: 38,
    color: "FFFFFF",
    bold: true,
    margin: 0,
    fit: "shrink",
  });
  titleSlide.addText(ticker, {
    x: 0.74,
    y: 3.05,
    w: 2.4,
    h: 0.38,
    fontSize: 16,
    color: "E0F2FE",
    bold: true,
    margin: 0,
  });
  titleSlide.addShape(pptx.ShapeType.roundRect, {
    x: 8.35,
    y: 1.35,
    w: 3.9,
    h: 3.7,
    rectRadius: 0.18,
    line: { color: "334155", width: 0.8 },
    fill: { color: "1E293B", transparency: 12 },
  });
  titleSlide.addText("Generated by TickerStats", {
    x: 8.72,
    y: 1.78,
    w: 2.9,
    h: 0.28,
    fontSize: 9,
    color: "BAE6FD",
    bold: true,
    margin: 0,
  });
  titleSlide.addText("Research output for investment committee review", {
    x: 8.72,
    y: 2.22,
    w: 2.85,
    h: 0.9,
    fontSize: 13,
    color: "FFFFFF",
    bold: true,
    margin: 0,
    fit: "shrink",
  });
  const genDate = getGeneratedDate(data);
  const formattedDate = formatDate(genDate);
  const { sectionCount, slideCount } = countSlidesAndSections(sections);
  if (genDate) {
    titleSlide.addText(
      `Generated: ${new Date(genDate).toLocaleDateString()}`,
      {
        x: 8.72,
        y: 3.78,
        w: 2.8,
        h: 0.22,
        fontSize: 8,
        color: "CBD5E1",
        margin: 0,
      },
    );
  }
  titleSlide.addText(
    `${sectionCount} section${sectionCount !== 1 ? "s" : ""} · ${slideCount} slide${slideCount !== 1 ? "s" : ""}`,
    {
      x: 8.72,
      y: 4.12,
      w: 2.8,
      h: 0.22,
      fontSize: 8,
      color: "94A3B8",
      margin: 0,
    },
  );

  // ---------- Section slides ----------
  let slideNo = 1;
  // Extract comps data for comps_table block rendering
  const compsData = (() => {
    try {
      const ci = (data as any).computed_inputs;
      if (!ci?.comps_table) return null;
      const raw = ci.comps_table;
      const headers = ["Symbol", "Price", "Mkt Cap", "EV", "Fwd P/E", "P/S", "P/B", "EV/EBITDA", "EV/Rev", "Margin", "ROE"];
      const rows: any[][] = [];
      const snapFields = ["sharePrice", "marketCap", "enterpriseValue", "forwardPE", "priceSales", "priceBook", "evEbitda", "evRevenue", "profitMargin", "roe"];
      const target = raw.target;
      if (target) {
        const snap = target.snapshot || {};
        rows.push([target.ticker, ...snapFields.map((f: string) => snap[f] ?? null)]);
      }
      for (const comp of (raw.comparables || [])) {
        const snap = comp.snapshot || {};
        rows.push([comp.ticker, ...snapFields.map((f: string) => snap[f] ?? null)]);
      }
      return rows.length ? { headers, rows, subject_index: 0 } : null;
    } catch { return null; }
  })();

  for (const section of sections) {
    // Section divider slide
    const dividerSlide = pptx.addSlide();
    dividerSlide.background = { color: PPT.navy };
    dividerSlide.addShape(pptx.ShapeType.rect, {
      x: 0,
      y: 0,
      w: 0.16,
      h: PPT.h,
      line: { color: PPT.accent, transparency: 100 },
      fill: { color: PPT.accent },
    });
    dividerSlide.addText("SECTION", {
      x: 0.72,
      y: 2.42,
      w: 2.2,
      h: 0.25,
      fontSize: 8,
      bold: true,
      color: "BAE6FD",
      margin: 0,
    });
    dividerSlide.addText(toTitleCase(section.section_id), {
      x: 0.72,
      y: 2.85,
      w: 8.8,
      h: 0.82,
      fontSize: 30,
      color: "FFFFFF",
      bold: true,
      margin: 0,
      fit: "shrink",
    });
    // Accent underline
    dividerSlide.addShape("line", {
      x: 0.72,
      y: 3.78,
      w: 1.6,
      h: 0,
      line: { color: PPT.accent, width: 2.5 },
    });
    // Slide count (hide noise when section is a single slide)
    const divSlideCount = (section.slides || []).length;
    if (divSlideCount > 1) {
      dividerSlide.addText(
        `${divSlideCount} slide${divSlideCount !== 1 ? "s" : ""}`,
        {
          x: 0.72,
          y: 4.05,
          w: 2.2,
          h: 0.25,
          fontSize: 9,
          color: "94A3B8",
          margin: 0,
        },
      );
    }

    for (const [index, slide] of (section.slides || []).entries()) {
      const pptSlide = pptx.addSlide();
      renderPptSlide(
        pptx,
        pptSlide,
        section,
        slide,
        slideNo,
        getSlideDesign(options.designSpec, section, slide, index),
        formattedDate,
        compsData,
      );
      slideNo += 1;
    }
  }

  pptx.writeFile({ fileName: filename });
}
