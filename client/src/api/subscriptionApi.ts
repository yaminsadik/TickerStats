import { API_BASE } from "../config/apiBase";

type AuthFetch = (url: string, options?: RequestInit) => Promise<Response>;

export interface CreateCheckoutSessionResponse {
  url: string;
  session_id: string;
}

export interface CreatePortalSessionResponse {
  url: string;
}

export type CheckoutItem = "pro" | "enterprise" | "deck_export";

export interface CreateCheckoutSessionOptions {
  deckId?: number;
}

async function jsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = (body as { detail?: string }).detail || `Request failed (${response.status})`;
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
