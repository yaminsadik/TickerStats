import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, Trash2, Eye, Clock, Loader2, Cpu } from "lucide-react";
import { Button, Card, Alert, Badge } from "../components/ui";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import { fetchDecks, deleteDeckFromDB, type DeckMeta } from "../api/userApi";

export default function DecksListPage() {
  const navigate = useNavigate();
  const { authenticatedFetch } = useAuthenticatedFetch();
  const [decks, setDecks] = useState<DeckMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDecks(authenticatedFetch);
      setDecks(data);
    } catch (err: any) {
      setError(err.message || "Failed to load decks");
    } finally {
      setLoading(false);
    }
  }, [authenticatedFetch]);

  useEffect(() => {
    load();
  }, [load]);

  const handleDelete = async (id: number) => {
    setDeletingId(id);
    try {
      await deleteDeckFromDB(authenticatedFetch, id);
      setDecks((prev) => prev.filter((d) => d.id !== id));
    } catch (err: any) {
      setError(err.message || "Failed to delete deck");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Deck History</h1>
          <p className="text-slate-400 mt-1">
            Previously generated pitch decks
          </p>
        </div>
        <Button onClick={() => navigate("/deck/new")} size="sm">
          <FileText className="w-4 h-4 mr-2" />
          New Deck
        </Button>
      </div>

      {error && (
        <Alert variant="error" title="Error">
          {error}
        </Alert>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
        </div>
      ) : decks.length === 0 ? (
        <Card className="text-center py-16 px-6">
          <div className="w-20 h-20 mx-auto mb-4 bg-slate-800 rounded-full flex items-center justify-center">
            <FileText className="w-10 h-10 text-slate-500" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">
            No Decks Generated Yet
          </h3>
          <p className="text-slate-400 mb-6 max-w-sm mx-auto">
            Generate a pitch deck from the Browse page or the Deck Wizard, and
            it will appear here.
          </p>
          <Button onClick={() => navigate("/deck/new")}>
            <FileText className="w-4 h-4 mr-2" />
            Generate Your First Deck
          </Button>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {decks.map((d) => (
            <Card key={d.id} className="flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between mb-2">
                  <div className="min-w-0 flex-1">
                    <span className="text-xs font-bold text-blue-400 uppercase tracking-wider">
                      {d.ticker}
                    </span>
                    <h3 className="text-base font-semibold text-white truncate mt-0.5">
                      {d.title}
                    </h3>
                  </div>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-500 mt-3">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    {new Date(d.created_at).toLocaleDateString()}
                  </span>
                  {d.llm_provider && (
                    <Badge variant="default" className="text-xs">
                      <Cpu className="w-3 h-3 mr-1" />
                      {d.llm_provider}
                    </Badge>
                  )}
                </div>
              </div>
              <div className="flex gap-2 mt-4 pt-3 border-t border-slate-800">
                <Button
                  variant="primary"
                  size="sm"
                  className="flex-1"
                  onClick={() => navigate(`/deck/db/${d.id}`)}
                >
                  <Eye className="w-4 h-4 mr-1" />
                  View
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDelete(d.id)}
                  disabled={deletingId === d.id}
                >
                  {deletingId === d.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
