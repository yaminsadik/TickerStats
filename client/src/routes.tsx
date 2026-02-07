import { createBrowserRouter, Navigate } from "react-router-dom";
import PageShell from "./components/layout/PageShell";
import ProtectedRoute from "./components/ProtectedRoute";
import LandingPage from "./pages/LandingPage";
import ContactPage from "./pages/ContactPage";
import BrowsePage from "./pages/BrowsePage";
import DeckWizardPage from "./pages/DeckWizardPage";
import DeckDraftPage from "./pages/DeckDraftPage";
import SavedSearchesPage from "./pages/SavedSearchesPage";
import WatchlistPage from "./pages/WatchlistPage";
import DecksListPage from "./pages/DecksListPage";
import DeckViewPage from "./pages/DeckViewPage";

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
        index: true,
        element: <Navigate to="/deck/new" replace />,
      },
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
    path: "/saved-searches",
    element: (
      <ProtectedRoute>
        <PageShell />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <SavedSearchesPage />,
      },
    ],
  },
  {
    path: "/watchlist",
    element: (
      <ProtectedRoute>
        <PageShell />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <WatchlistPage />,
      },
    ],
  },
  {
    path: "/decks",
    element: (
      <ProtectedRoute>
        <PageShell />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <DecksListPage />,
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
        path: "db/:id",
        element: <DeckViewPage />,
      },
      {
        path: ":id",
        element: <DeckDraftPage />,
      },
    ],
  },
]);
