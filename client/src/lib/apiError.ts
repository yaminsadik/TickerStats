/**
 * Standardized API error type and normalizer.
 * All query/mutation errors are wrapped through toApiError for consistency.
 */

export interface ApiError {
  status?: number;
  message: string;
  details?: unknown;
  requestId?: string;
  cause?: unknown;
}

/**
 * Normalize any thrown value into a consistent ApiError shape.
 * Handles: Error with .status, plain Error, thrown strings, unknown values.
 */
export function toApiError(e: unknown): ApiError {
  if (e instanceof Error) {
    return {
      status: (e as any).status as number | undefined,
      message: e.message || "An unexpected error occurred",
      cause: (e as any).cause,
    };
  }

  if (typeof e === "string") {
    return { message: e };
  }

  if (e && typeof e === "object" && "message" in e) {
    return {
      status: (e as any).status as number | undefined,
      message: String((e as any).message),
      details: (e as any).details,
    };
  }

  return { message: "An unexpected error occurred", cause: e };
}
