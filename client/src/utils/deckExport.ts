/**
 * Deck export utilities – PDF and PPTX generation from DeckExportData.
 * Uses jsPDF for PDF and PptxGenJS for PowerPoint.
 */
import type { DeckExportData } from "../components/ui/JsonViewerModal";
import { FIELD_LABELS } from "../types/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toTitleCase(str: string) {
  return str.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

interface NormalizedSection {
  section_id: string;
  slides: Array<{
    title: string;
    bullets: Array<{ text: string; source_needed?: boolean }>;
    speaker_notes?: string;
  }>;
  citations?: string[];
}

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

// ---------------------------------------------------------------------------
// Comps table → grid helper
// ---------------------------------------------------------------------------

interface CompsGrid {
  headers: string[];
  rows: string[][];
}

/**
 * Convert `computed_inputs.comps_table` into a simple grid of display strings.
 * Returns null when data is missing or empty.
 */
function compsTableToGrid(compsTable: unknown): CompsGrid | null {
  const ct = compsTable as Record<string, any> | undefined;
  if (!ct || !ct.target) return null;

  // Gather all company entries (target first, then comparables)
  const entries: Array<{ ticker: string; snapshot: Record<string, any>; performance?: Record<string, any> | null }> = [];
  if (ct.target) entries.push(ct.target);
  if (Array.isArray(ct.comparables)) {
    entries.push(...ct.comparables);
  }
  if (entries.length === 0) return null;

  // Derive snapshot field keys from the target's snapshot (or metrics_included hint)
  const snapshotFields: string[] =
    ct.metrics_included?.snapshot ??
    Object.keys(entries[0].snapshot || {});
  const perfFields: string[] =
    ct.metrics_included?.performance ?? [];

  const headers = [
    "Ticker",
    ...snapshotFields.map((f: string) => FIELD_LABELS[f] || toTitleCase(f)),
    ...perfFields.map((f: string) => FIELD_LABELS[f] || toTitleCase(f)),
  ];

  const rows: string[][] = entries.map((entry) => {
    const vals: string[] = [entry.ticker];
    for (const f of snapshotFields) {
      vals.push(formatCellValue(entry.snapshot?.[f], f));
    }
    for (const f of perfFields) {
      vals.push(formatCellValue(entry.performance?.[f], f));
    }
    return vals;
  });

  return { headers, rows };
}

/** Simple number formatter for the comps grid cells. */
function formatCellValue(val: unknown, field: string): string {
  if (val === null || val === undefined) return "—";
  const n = Number(val);
  if (isNaN(n)) return String(val);

  // Large currency values (marketCap, enterpriseValue)
  if (field === "marketCap" || field === "enterpriseValue") {
    const abs = Math.abs(n);
    if (abs >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
    if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    return `$${n.toFixed(2)}`;
  }
  if (field === "sharePrice" || field === "dcfPrice") return `$${n.toFixed(2)}`;

  // Percent-like metrics
  if (
    ["profitMargin", "roa", "roe", "return", "volatility", "maxDrawdown", "dcfUpside"].includes(field)
  ) {
    return `${(n * 100).toFixed(2)}%`;
  }

  // Ratios / multiples
  return n.toFixed(2);
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
  const margin = 15;
  const contentW = pageW - margin * 2;

  const sections = normalizeSections(data);
  const ticker = data.ticker || data.metadata?.ticker || "";
  const companyName = data.metadata?.company_name || ticker;

  // ---------- Title slide ----------
  doc.setFillColor(30, 58, 138); // dark blue
  doc.rect(0, 0, pageW, pageH, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(32);
  doc.text(companyName, pageW / 2, pageH / 2 - 15, { align: "center" });
  doc.setFontSize(18);
  doc.text(`Pitch Deck – ${ticker}`, pageW / 2, pageH / 2 + 5, { align: "center" });
  doc.setFontSize(10);
  const genDate = data.generated_at || data.metadata?.generated_at;
  if (genDate) {
    doc.text(
      `Generated: ${new Date(genDate).toLocaleDateString()}`,
      pageW / 2,
      pageH / 2 + 20,
      { align: "center" },
    );
  }

  // ---------- Section slides ----------
  for (const section of sections) {
    for (const slide of section.slides || []) {
      doc.addPage();
      doc.setFillColor(245, 247, 250);
      doc.rect(0, 0, pageW, pageH, "F");

      // Section header bar
      doc.setFillColor(30, 58, 138);
      doc.rect(0, 0, pageW, 18, "F");
      doc.setTextColor(255, 255, 255);
      doc.setFontSize(10);
      doc.text(toTitleCase(section.section_id), margin, 12);

      // Slide title
      doc.setTextColor(30, 58, 138);
      doc.setFontSize(20);
      doc.text(slide.title, margin, 32);

      // Bullets
      doc.setTextColor(50, 50, 50);
      doc.setFontSize(12);
      let y = 44;
      for (const bullet of slide.bullets || []) {
        const lines = doc.splitTextToSize(`• ${bullet.text}`, contentW - 5);
        for (const line of lines) {
          if (y > pageH - margin - 10) {
            doc.addPage();
            doc.setFillColor(245, 247, 250);
            doc.rect(0, 0, pageW, pageH, "F");
            y = margin;
          }
          doc.text(line, margin + 3, y);
          y += 7;
        }
        y += 2;
      }

      // Speaker notes (smaller, italic-ish)
      if (slide.speaker_notes) {
        y += 4;
        doc.setFontSize(9);
        doc.setTextColor(120, 120, 120);
        const noteLines = doc.splitTextToSize(
          `Notes: ${slide.speaker_notes}`,
          contentW,
        );
        for (const line of noteLines) {
          if (y > pageH - margin) break;
          doc.text(line, margin, y);
          y += 5;
        }
      }
    }

    // --- Comps table page for relative_heatmap section ---
    if (section.section_id === "relative_heatmap") {
      const grid = compsTableToGrid(data.computed_inputs?.comps_table);
      if (grid) {
        doc.addPage();
        doc.setFillColor(245, 247, 250);
        doc.rect(0, 0, pageW, pageH, "F");

        // Header bar
        doc.setFillColor(30, 58, 138);
        doc.rect(0, 0, pageW, 18, "F");
        doc.setTextColor(255, 255, 255);
        doc.setFontSize(10);
        doc.text("Relative Heatmap", margin, 12);

        // Title
        doc.setTextColor(30, 58, 138);
        doc.setFontSize(18);
        doc.text("Comparative Analysis", margin, 30);

        // Table layout
        const numCols = grid.headers.length;
        const colW = contentW / numCols;
        const rowH = 7;
        const fontSize = Math.min(8, Math.max(5, 120 / numCols)); // shrink font for wide tables
        doc.setFontSize(fontSize);

        let tableY = 38;

        // Header row
        doc.setFillColor(30, 58, 138);
        doc.rect(margin, tableY, contentW, rowH, "F");
        doc.setTextColor(255, 255, 255);
        for (let c = 0; c < numCols; c++) {
          doc.text(
            grid.headers[c],
            margin + c * colW + colW / 2,
            tableY + rowH - 2,
            { align: "center" },
          );
        }
        tableY += rowH;

        // Data rows
        for (let r = 0; r < grid.rows.length; r++) {
          // Alternate row background
          if (r % 2 === 0) {
            doc.setFillColor(255, 255, 255);
          } else {
            doc.setFillColor(237, 240, 245);
          }
          doc.rect(margin, tableY, contentW, rowH, "F");

          doc.setTextColor(50, 50, 50);
          for (let c = 0; c < numCols; c++) {
            const cellText = grid.rows[r][c] ?? "";
            doc.text(
              cellText,
              margin + c * colW + colW / 2,
              tableY + rowH - 2,
              { align: "center" },
            );
          }
          tableY += rowH;

          // Page break if out of room
          if (tableY > pageH - margin - rowH && r < grid.rows.length - 1) {
            doc.addPage();
            doc.setFillColor(245, 247, 250);
            doc.rect(0, 0, pageW, pageH, "F");
            tableY = margin;
          }
        }

        // Grid lines
        doc.setDrawColor(180, 180, 180);
        doc.setLineWidth(0.2);
        const tableTop = 38;
        const tableBottom = tableY;
        // Horizontal lines
        for (let r = 0; r <= grid.rows.length + 1; r++) {
          const ly = tableTop + r * rowH;
          if (ly <= tableBottom) {
            doc.line(margin, ly, margin + contentW, ly);
          }
        }
        // Vertical lines
        for (let c = 0; c <= numCols; c++) {
          const lx = margin + c * colW;
          doc.line(lx, tableTop, lx, tableBottom);
        }
      }
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

  const sections = normalizeSections(data);
  const ticker = data.ticker || data.metadata?.ticker || "";
  const companyName = data.metadata?.company_name || ticker;

  // ---------- Title slide ----------
  const titleSlide = pptx.addSlide();
  titleSlide.background = { color: "1E3A8A" };
  titleSlide.addText(companyName, {
    x: 0.5,
    y: 2.0,
    w: 12.33,
    h: 1.2,
    fontSize: 36,
    color: "FFFFFF",
    bold: true,
    align: "center",
  });
  titleSlide.addText(`Pitch Deck – ${ticker}`, {
    x: 0.5,
    y: 3.4,
    w: 12.33,
    h: 0.8,
    fontSize: 20,
    color: "CBD5E1",
    align: "center",
  });
  const genDate = data.generated_at || data.metadata?.generated_at;
  if (genDate) {
    titleSlide.addText(
      `Generated: ${new Date(genDate).toLocaleDateString()}`,
      {
        x: 0.5,
        y: 4.5,
        w: 12.33,
        h: 0.5,
        fontSize: 12,
        color: "94A3B8",
        align: "center",
      },
    );
  }

  // ---------- Section slides ----------
  for (const section of sections) {
    // Section divider slide
    const dividerSlide = pptx.addSlide();
    dividerSlide.background = { color: "1E3A8A" };
    dividerSlide.addText(toTitleCase(section.section_id), {
      x: 0.5,
      y: 2.8,
      w: 12.33,
      h: 1.2,
      fontSize: 28,
      color: "FFFFFF",
      bold: true,
      align: "center",
    });

    for (const slide of section.slides || []) {
      const pptSlide = pptx.addSlide();
      pptSlide.background = { color: "F8FAFC" };

      // Header bar
      pptSlide.addShape(pptx.ShapeType.rect, {
        x: 0,
        y: 0,
        w: 13.33,
        h: 0.7,
        fill: { color: "1E3A8A" },
      });
      pptSlide.addText(toTitleCase(section.section_id), {
        x: 0.4,
        y: 0.05,
        w: 6,
        h: 0.6,
        fontSize: 11,
        color: "FFFFFF",
      });

      // Slide title
      pptSlide.addText(slide.title, {
        x: 0.5,
        y: 1.0,
        w: 12.33,
        h: 0.7,
        fontSize: 22,
        color: "1E3A8A",
        bold: true,
      });

      // Bullets
      const bulletTexts = (slide.bullets || []).map((b) => ({
        text: b.text,
        options: {
          fontSize: 14,
          color: "334155" as string,
          bullet: { code: "2022" },
          breakLine: true,
          paraSpaceAfter: 6,
        },
      }));

      if (bulletTexts.length > 0) {
        pptSlide.addText(bulletTexts, {
          x: 0.7,
          y: 1.9,
          w: 11.93,
          h: 4.5,
          valign: "top",
        });
      }

      // Speaker notes
      if (slide.speaker_notes) {
        pptSlide.addNotes(slide.speaker_notes);
      }
    }

    // --- Comps table slide for relative_heatmap section ---
    if (section.section_id === "relative_heatmap") {
      const grid = compsTableToGrid(data.computed_inputs?.comps_table);
      if (grid) {
        const tableSlide = pptx.addSlide();
        tableSlide.background = { color: "F8FAFC" };

        // Header bar
        tableSlide.addShape(pptx.ShapeType.rect, {
          x: 0,
          y: 0,
          w: 13.33,
          h: 0.7,
          fill: { color: "1E3A8A" },
        });
        tableSlide.addText("Relative Heatmap", {
          x: 0.4,
          y: 0.05,
          w: 6,
          h: 0.6,
          fontSize: 11,
          color: "FFFFFF",
        });

        // Title
        tableSlide.addText("Comparative Analysis", {
          x: 0.5,
          y: 0.85,
          w: 12.33,
          h: 0.5,
          fontSize: 18,
          color: "1E3A8A",
          bold: true,
        });

        // Build PptxGenJS table rows
        // Scale font size for wide tables
        const numCols = grid.headers.length;
        const cellFontSize = Math.min(10, Math.max(6, 90 / numCols));

        type PptxTableCell = {
          text: string;
          options: Record<string, unknown>;
        };

        const headerRow: PptxTableCell[] = grid.headers.map((h) => ({
          text: h,
          options: {
            bold: true,
            color: "FFFFFF",
            fill: { color: "1E3A8A" },
            fontSize: cellFontSize,
            align: "center",
            valign: "middle",
            border: { pt: 0.5, color: "94A3B8" },
          },
        }));

        const dataRows: PptxTableCell[][] = grid.rows.map((row, rowIdx) =>
          row.map((cell) => ({
            text: cell,
            options: {
              fontSize: cellFontSize,
              color: "334155",
              fill: { color: rowIdx % 2 === 0 ? "FFFFFF" : "F1F5F9" },
              align: "center",
              valign: "middle",
              border: { pt: 0.5, color: "CBD5E1" },
            },
          })),
        );

        const tableRows = [headerRow, ...dataRows];

        // Auto-size columns to fill slide width
        const colW = 12.33 / numCols;

        tableSlide.addTable(tableRows as any, {
          x: 0.5,
          y: 1.5,
          w: 12.33,
          colW: Array(numCols).fill(colW),
          rowH: 0.35,
          autoPage: true,
          autoPageRepeatHeader: true,
        });
      }
    }
  }

  pptx.writeFile({ fileName: filename });
}
