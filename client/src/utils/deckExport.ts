/**
 * Deck export utilities – PDF and PPTX generation from DeckExportData.
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

  }

  pptx.writeFile({ fileName: filename });
}
