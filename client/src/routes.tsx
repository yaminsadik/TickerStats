import { createBrowserRouter, Navigate } from "react-router-dom";
import PageShell from "./components/layout/PageShell";
import ProtectedRoute from "./components/ProtectedRoute";
import LandingPage from "./pages/LandingPage";
import ContactPage from "./pages/ContactPage";
import BrowsePage from "./pages/BrowsePage";
import DeckWizardPage from "./pages/DeckWizardPage";
import DeckDraftPage from "./pages/DeckDraftPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <LandingPage />,
  },

  {
    path: "/contact",
    element: <ContactPage />,
  },
  {
    path: "/app",
    element: (
      <ProtectedRoute>
        <PageShell />
      </ProtectedRoute>
    ),
    children: [
      {
        path: "deck",
        element: <Navigate to="/deck/new" replace />,
      },
      {
        path: "compare",
        element: <Navigate to="/browse" replace />,
      },
    ],
  },
  {
    path: "/browse",
    element: (
      <ProtectedRoute>
        <PageShell />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <BrowsePage />,
      },
    ],
  },
  {
    path: "/deck",
    element: (
      <ProtectedRoute>
        <PageShell />
      </ProtectedRoute>
    ),
    children: [
      {
        path: "new",
        element: <DeckWizardPage />,
      },
      {
        path: ":id",
        element: <DeckDraftPage />,
      },
    ],
  },
]);
