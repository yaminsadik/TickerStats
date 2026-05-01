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

const PPT = {
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
  if (data.results && data.results.length > 0) {
    return data.results as NormalizedSection[];
  }
  if (data.sections && data.sections.length > 0) {
    return data.sections.map((s) => ({
      section_id: s.section_id,
      slides: s.slides as NormalizedSection["slides"],
      citations: s.citations,
    }));
  }
  return [];
}

function getGeneratedDate(data: DeckExportData) {
  return data.generated_at || data.metadata?.generated_at;
}

function getDeckTitle(data: DeckExportData) {
  const ticker = data.ticker || data.metadata?.ticker || "";
  const companyName = data.metadata?.company_name || ticker;
  return { ticker, companyName };
}

function cleanText(text: string) {
  return text.replace(/\s+/g, " ").trim();
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

function addPptHeader(pptx: any, slide: any, sectionName: string, slideNo?: number) {
  slide.background = { color: PPT.bg };
  slide.addShape(pptx.ShapeType.rect, {
    x: 0,
    y: 0,
    w: PPT.w,
    h: 0.42,
    line: { color: PPT.navy, transparency: 100 },
    fill: { color: PPT.navy },
  });
  slide.addText(sectionName, {
    x: 0.45,
    y: 0.1,
    w: 6.4,
    h: 0.2,
    fontSize: 7.5,
    bold: true,
    color: "E0F2FE",
    charSpace: 1,
  });
  if (slideNo !== undefined) {
    slide.addText(String(slideNo).padStart(2, "0"), {
      x: 12.25,
      y: 0.08,
      w: 0.55,
      h: 0.24,
      fontSize: 8,
      color: "BAE6FD",
      align: "right",
    });
  }
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
  slide.addShape("line", {
    x: 0.55,
    y: 1.35,
    w: 1.05,
    h: 0,
    line: { color: PPT.accent, width: 2.5 },
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

function renderPptCards(slide: any, deckSlide: NormalizedSlide) {
  const bullets = deckSlide.bullets || [];
  if (bullets.length === 0) return;

  const first = bullets[0];
  slide.addShape("roundRect", {
    x: 0.58,
    y: 1.62,
    w: 12.15,
    h: 1.18,
    rectRadius: 0.1,
    line: { color: "BFDBFE", width: 0.8 },
    fill: { color: "EFF6FF" },
  });
  slide.addText(shortText(stripPrefix(first.text), 185), {
    x: 0.92,
    y: 1.88,
    w: 11.35,
    h: 0.58,
    fontSize: 15,
    bold: true,
    color: PPT.blue,
    margin: 0,
    fit: "shrink",
  });
  addPptSourceFlag(slide, first, 11.15, 2.48);

  const rest = bullets.slice(1);
  const cardW = rest.length <= 2 ? 5.82 : 3.82;
  const startX = rest.length <= 2 ? 0.58 : 0.58;
  rest.forEach((bullet, index) => {
    addPptCard(
      slide,
      bullet,
      index,
      startX + index * (cardW + 0.25),
      3.25,
      cardW,
      1.72,
      [PPT.green, PPT.purple, PPT.amber][index % 3],
    );
  });
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
  const bullets = (deckSlide.bullets || []).slice(0, 5);
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
  const cells = [
    { key: "S" as const, title: "Strengths", x: 0.62, y: 1.62, color: PPT.green },
    { key: "W" as const, title: "Weaknesses", x: 6.88, y: 1.62, color: PPT.amber },
    { key: "O" as const, title: "Opportunities", x: 0.62, y: 4.12, color: PPT.blue },
    { key: "T" as const, title: "Threats", x: 6.88, y: 4.12, color: PPT.red },
  ];

  cells.forEach((cell) => {
    slide.addShape("roundRect", {
      x: cell.x,
      y: cell.y,
      w: 5.85,
      h: 2.05,
      rectRadius: 0.1,
      line: { color: PPT.border, width: 0.8 },
      fill: { color: PPT.card },
    });
    slide.addText(cell.title, {
      x: cell.x + 0.3,
      y: cell.y + 0.2,
      w: 4.6,
      h: 0.28,
      fontSize: 10,
      bold: true,
      color: cell.color,
      margin: 0,
    });
    const items = groups[cell.key].length
      ? groups[cell.key]
      : (deckSlide.bullets || []).slice(0, 2).map((b) => stripPrefix(b.text));
    slide.addText(
      items.slice(0, 2).map((text) => ({ text: shortText(text, 70), options: { breakLine: true } })),
      {
        x: cell.x + 0.32,
        y: cell.y + 0.72,
        w: 5.2,
        h: 1.05,
        fontSize: 9.2,
        color: PPT.text,
        bullet: { type: "ul" },
        fit: "shrink",
        margin: 0,
      },
    );
  });
}

function renderPptValuation(slide: any, deckSlide: NormalizedSlide) {
  const bullets = deckSlide.bullets || [];
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

function renderPptSlide(
  pptx: any,
  pptSlide: any,
  section: NormalizedSection,
  slide: NormalizedSlide,
  slideNo: number,
) {
  addPptHeader(pptx, pptSlide, toTitleCase(section.section_id), slideNo);
  addPptTitle(pptSlide, slide.title);

  const kind = slideKind(section, slide);
  if (kind === "timeline") renderPptTimeline(pptSlide, slide);
  else if (kind === "swot") renderPptSwot(pptSlide, slide);
  else if (kind === "two_column") renderPptTwoColumn(pptSlide, slide);
  else if (kind === "valuation") renderPptValuation(pptSlide, slide);
  else renderPptCards(pptSlide, slide);

  pptSlide.addText("TickerStats", {
    x: 0.58,
    y: 7.02,
    w: 1.5,
    h: 0.18,
    fontSize: 6.5,
    color: PPT.muted,
    margin: 0,
  });
  addPptNotes(pptSlide, slide.speaker_notes);
}

function pdfSet(doc: any, color: [number, number, number]) {
  doc.setTextColor(color[0], color[1], color[2]);
}

function pdfFill(doc: any, color: [number, number, number]) {
  doc.setFillColor(color[0], color[1], color[2]);
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
  doc.text(shortText(title, 95), 14, 26);
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
  fontSize = 10.5,
) {
  pdfFill(doc, PDF.card);
  doc.setDrawColor(...PDF.border);
  doc.roundedRect(x, y, w, h, 2, 2, "FD");
  pdfSet(doc, PDF.text);
  doc.setFontSize(fontSize);
  const lines = doc.splitTextToSize(shortText(stripPrefix(text), 170), w - 8);
  doc.text(lines.slice(0, 5), x + 4, y + 8);
}

function renderPdfCards(doc: any, slide: NormalizedSlide) {
  const bullets = slide.bullets || [];
  if (bullets[0]) {
    pdfFill(doc, [239, 246, 255]);
    doc.setDrawColor(191, 219, 254);
    doc.roundedRect(14, 39, 269, 27, 2, 2, "FD");
    pdfSet(doc, PDF.blue);
    doc.setFontSize(13);
    doc.text(doc.splitTextToSize(shortText(stripPrefix(bullets[0].text), 190), 252), 22, 50);
  }

  bullets.slice(1, 4).forEach((bullet, index) => {
    pdfCard(doc, bullet.text, 14 + index * 91, 82, 82, 42);
  });
}

function renderPdfTwoColumn(doc: any, slide: NormalizedSlide) {
  const [left, right] = splitForColumns(slide.bullets || []);
  [
    { title: "Market View", bullets: left, x: 14 },
    { title: "Variant View", bullets: right, x: 151 },
  ].forEach((col) => {
    pdfCard(doc, "", col.x, 39, 132, 95);
    pdfSet(doc, PDF.blue);
    doc.setFontSize(10);
    doc.text(col.title.toUpperCase(), col.x + 5, 48);
    pdfSet(doc, PDF.text);
    doc.setFontSize(9.3);
    let y = 58;
    for (const bullet of col.bullets) {
      const lines = doc.splitTextToSize(shortText(stripPrefix(bullet.text), 115), 118);
      doc.text(lines.slice(0, 3), col.x + 6, y);
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
  const cells = [
    { key: "S" as const, title: "Strengths", x: 14, y: 39 },
    { key: "W" as const, title: "Weaknesses", x: 151, y: 39 },
    { key: "O" as const, title: "Opportunities", x: 14, y: 101 },
    { key: "T" as const, title: "Threats", x: 151, y: 101 },
  ];
  cells.forEach((cell) => {
    pdfCard(doc, "", cell.x, cell.y, 132, 49);
    pdfSet(doc, PDF.blue);
    doc.setFontSize(10);
    doc.text(cell.title, cell.x + 6, cell.y + 10);
    pdfSet(doc, PDF.text);
    doc.setFontSize(8.8);
    const lines = groups[cell.key].slice(0, 2).flatMap((item) =>
      doc.splitTextToSize(`- ${shortText(item, 70)}`, 116),
    );
    doc.text(lines.slice(0, 5), cell.x + 6, cell.y + 22);
  });
}

function renderPdfValuation(doc: any, slide: NormalizedSlide) {
  const bullets = slide.bullets || [];
  if (bullets[0]) pdfCard(doc, bullets[0].text, 14, 39, 120, 95, 13);
  bullets.slice(1, 4).forEach((bullet, index) => {
    pdfCard(doc, bullet.text, 150, 39 + index * 33, 133, 26, 9.5);
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

  pdfSet(doc, PDF.muted);
  doc.setFontSize(7);
  doc.text("TickerStats", 14, pageH - 8);
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

  // ---------- Title slide ----------
  pdfFill(doc, PDF.navy);
  doc.rect(0, 0, pageW, pageH, "F");
  pdfFill(doc, PDF.accent);
  doc.rect(0, 0, 7, pageH, "F");
  pdfSet(doc, [255, 255, 255]);
  doc.setFontSize(34);
  doc.text(companyName, 28, pageH / 2 - 20);
  doc.setFontSize(15);
  doc.text(`Investment Pitch Deck | ${ticker}`, 28, pageH / 2);
  doc.setFontSize(10);
  const genDate = getGeneratedDate(data);
  if (genDate) {
    doc.text(
      `Generated: ${new Date(genDate).toLocaleDateString()}`,
      28,
      pageH / 2 + 14,
    );
  }

  // ---------- Section slides ----------
  for (const section of sections) {
    for (const slide of section.slides || []) {
      doc.addPage();
      renderPdfSlide(doc, section, slide);
    }
  }

  doc.save(filename);
}

// ---------------------------------------------------------------------------
// PPTX export
// ---------------------------------------------------------------------------

export async function exportDeckToPPTX(
  data: DeckExportData,
  filename: string,
) {
  const PptxGenJS = (await import("pptxgenjs")).default;

  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 inches
  pptx.author = "TickerStats";
  pptx.subject = "Investment pitch deck";
  pptx.theme = {
    headFontFace: "Aptos Display",
    bodyFontFace: "Aptos",
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
  if (genDate) {
    titleSlide.addText(
      `Generated: ${new Date(genDate).toLocaleDateString()}`,
      {
        x: 8.72,
        y: 4.18,
        w: 2.8,
        h: 0.22,
        fontSize: 8,
        color: "CBD5E1",
        margin: 0,
      },
    );
  }

  // ---------- Section slides ----------
  let slideNo = 1;
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

    for (const slide of section.slides || []) {
      const pptSlide = pptx.addSlide();
      renderPptSlide(pptx, pptSlide, section, slide, slideNo);
      slideNo += 1;
    }
  }

  pptx.writeFile({ fileName: filename });
}
