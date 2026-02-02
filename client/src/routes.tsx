import { createBrowserRouter, Navigate } from "react-router-dom";
import PageShell from "./components/layout/PageShell";
import BrowsePage from "./pages/BrowsePage";
import DeckWizardPage from "./pages/DeckWizardPage";
import DeckDraftPage from "./pages/DeckDraftPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <PageShell />,
    children: [
      {
        index: true,
        element: <Navigate to="/browse" replace />,
      },
      {
        path: "browse",
        element: <BrowsePage />,
      },
      {
        path: "deck/new",
        element: <DeckWizardPage />,
      },
      {
        path: "deck/:id",
        element: <DeckDraftPage />,
      },
    ],
  },
]);
