import { API_BASE } from "../config/apiBase";

type AuthFetch = (url: string, options?: RequestInit) => Promise<Response>;

export interface CreateCheckoutSessionResponse {
  url: string;
  session_id: string;
}

export interface CreatePortalSessionResponse {
  url: string;
}

export type CheckoutItem = "pro" | "enterprise" | "deck_export" | "usage_pack";

export interface CreateCheckoutSessionOptions {
  deckId?: number;
}

function formatErrorDetail(detail: unknown): string | null {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          const path =
            "loc" in item && Array.isArray((item as { loc?: unknown }).loc)
              ? `${(item as { loc: unknown[] }).loc.join(".")}: `
              : "";
          return `${path}${String((item as { msg: unknown }).msg)}`;
        }
        return null;
      })
      .filter(Boolean);

    return messages.length > 0 ? messages.join("; ") : null;
  }

  if (detail && typeof detail === "object") {
    if ("message" in detail) {
      return String((detail as { message: unknown }).message);
    }
    if ("msg" in detail) {
      return String((detail as { msg: unknown }).msg);
    }
    return JSON.stringify(detail);
  }

  return null;
}

async function jsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message =
      formatErrorDetail((body as { detail?: unknown }).detail) ||
      `Request failed (${response.status})`;
    throw new Error(message);
  }
  return response.json();
}

export const subscriptionApi = {
  async createCheckoutSession(
    authFetch: AuthFetch,
    item: CheckoutItem,
    options: CreateCheckoutSessionOptions = {},
  ): Promise<CreateCheckoutSessionResponse> {
    const body =
      item === "deck_export"
        ? { product: item, deck_id: options.deckId }
        : item === "usage_pack"
          ? { product: item }
          : { tier: item };
    const response = await authFetch(`${API_BASE}/api/v1/stripe/create-checkout-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return jsonOrThrow<CreateCheckoutSessionResponse>(response);
  },

  async createPortalSession(
    authFetch: AuthFetch,
  ): Promise<CreatePortalSessionResponse> {
    const response = await authFetch(`${API_BASE}/api/v1/stripe/create-portal-session`, {
      method: "POST",
    });
    return jsonOrThrow<CreatePortalSessionResponse>(response);
  },
};
