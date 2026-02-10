import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { FileText, Trash2, Eye, Clock, Loader2, Cpu } from "lucide-react";
import { Button, Card, Alert, Badge } from "../components/ui";
import { useDeckList, useDeleteDeck } from "../queries/useDeckQueries";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import { fetchDeck } from "../api/userApi";
import { deckFullSchema, type DeckMetaParsed } from "../schemas/deck";
import { parseOrThrow } from "../lib/parse";
import { queryKeys } from "../lib/queryKeys";

export default function DecksListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { authenticatedFetch } = useAuthenticatedFetch();
  const { data: decks, isLoading: loading, error: queryError } = useDeckList();
  const deleteMutation = useDeleteDeck();

  const prefetchDeck = (id: number) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.decks.detail(id),
      queryFn: () =>
        fetchDeck(authenticatedFetch, id).then((d) =>
          parseOrThrow(deckFullSchema, d, "deck"),
        ),
      staleTime: 60 * 1000,
    });
  };

  const error =
    queryError instanceof Error ? queryError.message : queryError ? String(queryError) : null;
  const deleteError =
    deleteMutation.isError && deleteMutation.error instanceof Error
      ? deleteMutation.error.message
      : null;

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

      {(error || deleteError) && (
        <Alert variant="error" title="Error">
          {error || deleteError}
        </Alert>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
        </div>
      ) : !decks || decks.length === 0 ? (
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
          {decks.map((d: DeckMetaParsed) => (
            <div key={d.id} onMouseEnter={() => prefetchDeck(d.id)}>
            <Card className="flex flex-col justify-between">
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
                  onClick={() => deleteMutation.mutate(d.id)}
                  disabled={
                    deleteMutation.isPending &&
                    deleteMutation.variables === d.id
                  }
                >
                  {deleteMutation.isPending &&
                  deleteMutation.variables === d.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </Button>
              </div>
            </Card>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
