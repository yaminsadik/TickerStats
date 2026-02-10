/**
 * Authenticated API client hook for making authenticated requests to the backend.
 * Automatically includes Auth0 JWT token in Authorization header.
 */
import { useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { API_BASE } from "../config/apiBase";

const AUTH0_SCOPE = "openid profile email offline_access";

// Avoid multiple simultaneous redirects when several queries fail at once.
let tokenRecoveryRedirectInProgress = false;

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  return String(error);
}

function getErrorCode(error: unknown): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "error" in error &&
    typeof (error as { error: unknown }).error === "string"
  ) {
    return (error as { error: string }).error;
  }
  return "";
}

function isRecoverableTokenError(error: unknown): boolean {
  const code = getErrorCode(error);
  if (code === "missing_refresh_token" || code === "invalid_grant") {
    return true;
  }

  const message = getErrorMessage(error);
  return /missing refresh token|missing_refresh_token|invalid_grant/i.test(
    message,
  );
}

// Log configuration in development mode
if (import.meta.env.DEV) {
  console.log("🔧 API Configuration:", {
    API_BASE,
    AUTH0_AUDIENCE: import.meta.env.VITE_AUTH0_AUDIENCE,
    AUTH0_DOMAIN: import.meta.env.VITE_AUTH0_DOMAIN,
  });
}

interface FetchOptions extends RequestInit {
  requireAuth?: boolean;
}

export function useAuthenticatedFetch() {
  const { getAccessTokenSilently, isAuthenticated, loginWithRedirect } =
    useAuth0();

  /**
   * Make an authenticated API request.
   * @param url - API endpoint (relative to API_BASE or absolute)
   * @param options - Fetch options with optional requireAuth flag
   */
  const authenticatedFetch = useCallback(async (
    url: string,
    options: FetchOptions = {}
  ): Promise<Response> => {
    const { requireAuth = true, ...fetchOptions } = options;

    if (requireAuth && !isAuthenticated) {
      throw new Error("Authentication required");
    }

    // Build full URL
    const fullUrl = url.startsWith("http") ? url : `${API_BASE}${url}`;

    // Get access token if authenticated and required
    let token: string | undefined;
    if (requireAuth && isAuthenticated) {
      try {
        token = await getAccessTokenSilently({
          authorizationParams: {
            audience: import.meta.env.VITE_AUTH0_AUDIENCE,
            scope: AUTH0_SCOPE,
          },
        });
        if (!token) {
          throw new Error("Token retrieval returned undefined");
        }
      } catch (error) {
        if (isRecoverableTokenError(error)) {
          console.warn(
            "Recoverable Auth0 token error. Redirecting to refresh session.",
            error,
          );

          if (!tokenRecoveryRedirectInProgress) {
            tokenRecoveryRedirectInProgress = true;
            try {
              await loginWithRedirect({
                appState: {
                  returnTo:
                    window.location.pathname +
                    window.location.search +
                    window.location.hash,
                },
                authorizationParams: {
                  audience: import.meta.env.VITE_AUTH0_AUDIENCE,
                  scope: AUTH0_SCOPE,
                },
              });
            } catch (redirectError) {
              tokenRecoveryRedirectInProgress = false;
              throw new Error(
                `Authentication failed: ${getErrorMessage(redirectError)}.`,
              );
            }
          }

          throw new Error("Authentication session expired. Redirecting to sign in.");
        }

        console.error("Failed to get access token:", error);
        throw new Error(`Authentication failed: ${getErrorMessage(error)}.`);
      }
    }

    // Add Authorization header if token exists
    const headers = new Headers(fetchOptions.headers);
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    // Make the request
    const response = await fetch(fullUrl, {
      ...fetchOptions,
      headers,
    });

    // Handle 401 Unauthorized
    if (response.status === 401 && requireAuth) {
      let detail = "Unauthorized - please log in";
      try {
        const body = await response.clone().json();
        if (body?.detail) {
          detail = body.detail;
        }
      } catch {
        // ignore JSON parse errors
      }
      console.error(`401 Unauthorized from ${fullUrl}:`, detail);
      throw new Error(`Authentication error: ${detail}`);
    }

    // Handle other HTTP errors with better messages
    if (!response.ok) {
      let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const body = await response.clone().json();
        if (body?.detail) {
          errorDetail = body.detail;
        }
      } catch {
        // ignore JSON parse errors
      }
      console.error(`Request to ${fullUrl} failed:`, errorDetail);
    }

    return response;
  }, [getAccessTokenSilently, isAuthenticated, loginWithRedirect]);

  return { authenticatedFetch, isAuthenticated };
}

/**
 * Convenience hooks for common HTTP methods
 */
export function useAuthenticatedApi() {
  const { authenticatedFetch, isAuthenticated } = useAuthenticatedFetch();

  const get = async <T = any>(url: string, requireAuth = true): Promise<T> => {
    const response = await authenticatedFetch(url, { requireAuth });
    if (!response.ok) {
      throw new Error(`GET ${url} failed: ${response.statusText}`);
    }
    return response.json();
  };

  const post = async <T = any>(
    url: string,
    data: any,
    requireAuth = true
  ): Promise<T> => {
    const response = await authenticatedFetch(url, {
      method: "POST",
      body: JSON.stringify(data),
      requireAuth,
    });
    if (!response.ok) {
      throw new Error(`POST ${url} failed: ${response.statusText}`);
    }
    return response.json();
  };

  const put = async <T = any>(
    url: string,
    data: any,
    requireAuth = true
  ): Promise<T> => {
    const response = await authenticatedFetch(url, {
      method: "PUT",
      body: JSON.stringify(data),
      requireAuth,
    });
    if (!response.ok) {
      throw new Error(`PUT ${url} failed: ${response.statusText}`);
    }
    return response.json();
  };

  const del = async (url: string, requireAuth = true): Promise<void> => {
    const response = await authenticatedFetch(url, {
      method: "DELETE",
      requireAuth,
    });
    if (!response.ok) {
      throw new Error(`DELETE ${url} failed: ${response.statusText}`);
    }
  };

  return { get, post, put, del, isAuthenticated, authenticatedFetch };
}
