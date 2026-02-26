const DEFAULT_API_BASE = "http://localhost:5000";

/**
 * Supports both legacy and current env names for compatibility.
 * Prefer VITE_API_BASE in new deployments.
 */
export const API_BASE =
  import.meta.env.VITE_API_BASE ||
  import.meta.env.VITE_API_BASE_URL ||
  DEFAULT_API_BASE;

if (typeof window !== "undefined") {
  const host = window.location.hostname;
  const runningLocally = host === "localhost" || host === "127.0.0.1";
  const pointsToLocalApi = API_BASE.includes("localhost") || API_BASE.includes("127.0.0.1");

  if (!runningLocally && pointsToLocalApi) {
    console.warn(
      `[config] API_BASE resolved to "${API_BASE}" on host "${host}". ` +
        "Set VITE_API_BASE or VITE_API_BASE_URL to your deployed backend URL."
    );
  }
}
