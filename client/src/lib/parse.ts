/**
 * Safe Zod parsing helper with dev-friendly error logging.
 * Replaces raw schema.parse() calls in query functions.
 */
import type { ZodSchema } from "zod";
import { toApiError } from "./apiError";

/**
 * Parse data with a Zod schema, throwing a user-friendly ApiError on failure.
 * In dev mode, logs detailed Zod issues and payload keys to the console.
 */
export function parseOrThrow<T>(
  schema: ZodSchema<T>,
  data: unknown,
  context: string,
): T {
  const result = schema.safeParse(data);
  if (result.success) return result.data;

  // Dev-only detailed diagnostics
  if (import.meta.env.DEV) {
    console.error(
      `[Zod] Validation failed for "${context}":`,
      result.error.issues,
      "Payload keys:",
      data && typeof data === "object" ? Object.keys(data) : typeof data,
    );
  }

  const err = new Error("Data validation failed. Please refresh.");
  throw toApiError(err);
}
