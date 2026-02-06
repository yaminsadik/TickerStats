/**
 * Authenticated API client hook for making authenticated requests to the backend.
 * Automatically includes Auth0 JWT token in Authorization header.
 */
import { useAuth0 } from "@auth0/auth0-react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

interface FetchOptions extends RequestInit {
  requireAuth?: boolean;
}

export function useAuthenticatedFetch() {
  const { getAccessTokenSilently, isAuthenticated } = useAuth0();

  /**
   * Make an authenticated API request.
   * @param url - API endpoint (relative to API_BASE_URL or absolute)
   * @param options - Fetch options with optional requireAuth flag
   */
  const authenticatedFetch = async (
    url: string,
    options: FetchOptions = {}
  ): Promise<Response> => {
    const { requireAuth = true, ...fetchOptions } = options;

    // Build full URL
    const fullUrl = url.startsWith("http") ? url : `${API_BASE_URL}${url}`;

    // Get access token if authenticated and required
    let token: string | undefined;
    if (requireAuth && isAuthenticated) {
      try {
        token = await getAccessTokenSilently({
          authorizationParams: {
            audience: import.meta.env.VITE_AUTH0_AUDIENCE,
          },
        });
      } catch (error) {
        console.error("Failed to get access token:", error);
        throw new Error("Authentication required");
      }
    }

    // Add Authorization header if token exists
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...fetchOptions.headers,
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    // Make the request
    const response = await fetch(fullUrl, {
      ...fetchOptions,
      headers,
    });

    // Handle 401 Unauthorized
    if (response.status === 401 && requireAuth) {
      throw new Error("Unauthorized - please log in");
    }

    return response;
  };

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
