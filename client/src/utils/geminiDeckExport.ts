import type { DeckExportData } from "../components/ui";
import type { PptxDesignSpec } from "./deckExport";

type AuthenticatedFetch = (url: string, options?: RequestInit) => Promise<Response>;

function getErrorMessage(body: unknown, fallback: string): string {
  if (
    typeof body === "object" &&
    body !== null &&
    "detail" in body &&
    typeof (body as { detail?: unknown }).detail === "object" &&
    (body as { detail?: { error?: unknown } }).detail !== null &&
    typeof (body as { detail: { error?: unknown } }).detail.error === "string"
  ) {
    return (body as { detail: { error: string } }).detail.error;
  }
  if (
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    typeof (body as { error?: unknown }).error === "string"
  ) {
    return (body as { error: string }).error;
  }
  return fallback;
}

export async function fetchPptxDesignSpec(
  authenticatedFetch: AuthenticatedFetch,
  deck: DeckExportData,
  title: string,
): Promise<PptxDesignSpec> {
  const response = await authenticatedFetch("/api/v1/deck/export/pptx-design-spec", {
    method: "POST",
    body: JSON.stringify({
      deck,
      title: title.replace(/\.(pptx|pdf|zip)$/i, ""),
    }),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(
      getErrorMessage(body, `Gemini PPTX design spec failed: HTTP ${response.status}`),
    );
  }

  return body as PptxDesignSpec;
}
