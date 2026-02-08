import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { Auth0Provider } from "@auth0/auth0-react";
import "./index.css";
import { router } from "./routes";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// Auth0 configuration from environment variables
const auth0Domain = import.meta.env.VITE_AUTH0_DOMAIN || "";
const auth0ClientId = import.meta.env.VITE_AUTH0_CLIENT_ID || "";
const auth0Audience = import.meta.env.VITE_AUTH0_AUDIENCE || "";

// Validate Auth0 configuration
if (!auth0Domain || !auth0ClientId) {
  console.warn("⚠️ Auth0 not configured. Check .env file:");
  console.warn("  VITE_AUTH0_DOMAIN:", auth0Domain || "(missing)");
  console.warn("  VITE_AUTH0_CLIENT_ID:", auth0ClientId || "(missing)");
  console.warn("  VITE_AUTH0_AUDIENCE:", auth0Audience || "(missing)");
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {auth0Domain && auth0ClientId ? (
      <Auth0Provider
        domain={auth0Domain}
        clientId={auth0ClientId}
        authorizationParams={{
          redirect_uri: window.location.origin,
          audience: auth0Audience,
        }}
        useRefreshTokens={true}
        cacheLocation="localstorage"
      >
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
          {import.meta.env.DEV && (
            <ReactQueryDevtools initialIsOpen={false} />
          )}
        </QueryClientProvider>
      </Auth0Provider>
    ) : (
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
        {import.meta.env.DEV && (
          <ReactQueryDevtools initialIsOpen={false} />
        )}
      </QueryClientProvider>
    )}
  </StrictMode>,
);
