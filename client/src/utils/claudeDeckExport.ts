import type { DeckExportData } from "../components/ui";

export type ClaudeDeckExportFormat = "pptx" | "pdf" | "both";

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

function filenameFromDisposition(disposition: string | null): string | null {
  if (!disposition) return null;
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] || null;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export async function exportDeckWithClaude(
  authenticatedFetch: AuthenticatedFetch,
  deck: DeckExportData,
  exportFormat: ClaudeDeckExportFormat,
  fallbackFilename: string,
) {
  const response = await authenticatedFetch("/api/v1/deck/export/claude", {
    method: "POST",
    body: JSON.stringify({
      deck,
      export_format: exportFormat,
      title: fallbackFilename.replace(/\.(pptx|pdf|zip)$/i, ""),
    }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      getErrorMessage(body, `Claude export failed: HTTP ${response.status}`),
    );
  }

  const blob = await response.blob();
  const filename =
    filenameFromDisposition(response.headers.get("content-disposition")) ||
    fallbackFilename;
  downloadBlob(blob, filename);
}
