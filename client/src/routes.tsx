import { createBrowserRouter, Navigate } from "react-router-dom";
import PageShell from "./components/layout/PageShell";
import LandingPage from "./pages/LandingPage";
import BrowsePage from "./pages/BrowsePage";
import DeckWizardPage from "./pages/DeckWizardPage";
import DeckDraftPage from "./pages/DeckDraftPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <LandingPage />,
  },
  {
    path: "/app",
    element: <PageShell />,
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
    element: <PageShell />,
    children: [
      {
        index: true,
        element: <BrowsePage />,
      },
    ],
  },
  {
    path: "/deck",
    element: <PageShell />,
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
