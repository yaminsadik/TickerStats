const DEFAULT_API_BASE = "http://localhost:5000";

const envBase =
  import.meta.env.VITE_API_BASE || import.meta.env.VITE_API_BASE_URL;

function isLocalBackendUrl(base: string | undefined): boolean {
  if (!base) return true;
  return base.includes("localhost") || base.includes("127.0.0.1");
}

/**
 * Prefer VITE_API_BASE / VITE_API_BASE_URL in production or when using a remote API in dev.
 * In local dev, use same-origin requests so Vite can proxy `/api` → the FastAPI container
 * (avoids browser CORS / Private Network Access edge cases against :5000).
 */
export const API_BASE =
  import.meta.env.DEV && isLocalBackendUrl(envBase)
    ? ""
    : envBase || DEFAULT_API_BASE;

/**
 * Path must start with `/` (e.g. `/api/relative`).
 */
export function apiUrl(path: string): URL {
  const pathname = path.startsWith("/") ? path : `/${path}`;
  if (API_BASE) {
    const base = API_BASE.replace(/\/$/, "");
    return new URL(`${base}${pathname}`);
  }
  if (typeof window !== "undefined") {
    return new URL(pathname, window.location.origin);
  }
  return new URL(pathname, "http://localhost");
}

if (typeof window !== "undefined") {
  const host = window.location.hostname;
  const runningLocally = host === "localhost" || host === "127.0.0.1";
  const pointsToLocalApi = isLocalBackendUrl(
    API_BASE || envBase || DEFAULT_API_BASE,
  );

  if (!runningLocally && pointsToLocalApi && API_BASE !== "") {
    console.warn(
      `[config] API_BASE resolved to "${API_BASE}" on host "${host}". ` +
        "Set VITE_API_BASE or VITE_API_BASE_URL to your deployed backend URL.",
    );
  }
}
