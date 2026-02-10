const DEFAULT_API_BASE = "http://localhost:5000";

/**
 * Supports both legacy and current env names for compatibility.
 * Prefer VITE_API_BASE in new deployments.
 */
export const API_BASE =
  import.meta.env.VITE_API_BASE ||
  import.meta.env.VITE_API_BASE_URL ||
  DEFAULT_API_BASE;

