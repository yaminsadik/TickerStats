import { useState } from "react";
import {
  Star,
  Trash2,
  Plus,
  Loader2,
  Edit3,
  Check,
  X,
  Clock,
} from "lucide-react";
import { Button, Card, Alert, Input } from "../components/ui";
import {
  useWatchlist,
  useAddToWatchlistFull,
  useUpdateWatchlistNotes,
  useRemoveFromWatchlist,
} from "../queries/useWatchlistQueries";
import type { WatchlistItemParsed } from "../schemas/userResources";

export default function WatchlistPage() {
  const { data: items, isLoading: loading, error: queryError } = useWatchlist();
  const addMutation = useAddToWatchlistFull();
  const updateNotesMutation = useUpdateWatchlistNotes();
  const removeMutation = useRemoveFromWatchlist();

  // Add form
  const [newTicker, setNewTicker] = useState("");
  const [newNotes, setNewNotes] = useState("");

  // Inline edit
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNotes, setEditNotes] = useState("");

  // Derive error from any failing mutation or query
  const error =
    queryError instanceof Error
      ? queryError.message
      : addMutation.isError && addMutation.error instanceof Error
        ? addMutation.error.message
        : updateNotesMutation.isError &&
            updateNotesMutation.error instanceof Error
          ? updateNotesMutation.error.message
          : removeMutation.isError && removeMutation.error instanceof Error
            ? removeMutation.error.message
            : null;

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTicker.trim()) return;
    addMutation.mutate(
      {
        ticker: newTicker.trim(),
        notes: newNotes.trim() || undefined,
      },
      {
        onSuccess: () => {
          setNewTicker("");
          setNewNotes("");
        },
      },
    );
  };

  const startEdit = (item: { id: number; notes: string | null }) => {
    setEditingId(item.id);
    setEditNotes(item.notes || "");
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditNotes("");
  };

  const saveNotes = (id: number) => {
    updateNotesMutation.mutate(
      { id, notes: editNotes.trim() || null },
      {
        onSuccess: () => {
          setEditingId(null);
        },
      },
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Watchlist</h1>
        <p className="text-slate-400 mt-1">
          Track tickers you're interested in
        </p>
      </div>

      {error && (
        <Alert variant="error" title="Error">
          {error}
        </Alert>
      )}

      {/* Add Ticker Form */}
      <Card>
        <form onSubmit={handleAdd} className="flex flex-col sm:flex-row gap-3">
          <Input
            placeholder="Ticker (e.g. AAPL)"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            className="flex-shrink-0 sm:w-36"
            disabled={addMutation.isPending}
          />
          <Input
            placeholder="Notes (optional)"
            value={newNotes}
            onChange={(e) => setNewNotes(e.target.value)}
            className="flex-1"
            disabled={addMutation.isPending}
          />
          <Button
            type="submit"
            disabled={addMutation.isPending || !newTicker.trim()}
          >
            {addMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <Plus className="w-4 h-4 mr-2" />
            )}
            Add
          </Button>
        </form>
      </Card>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
        </div>
      ) : !items || items.length === 0 ? (
        <Card className="text-center py-16 px-6">
          <div className="w-20 h-20 mx-auto mb-4 bg-slate-800 rounded-full flex items-center justify-center">
            <Star className="w-10 h-10 text-slate-500" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">
            Your Watchlist is Empty
          </h3>
          <p className="text-slate-400 max-w-sm mx-auto">
            Add tickers above or use the "Add to Watchlist" button on the Browse
            page.
          </p>
        </Card>
      ) : (
        <div className="space-y-2">
          {items.map((item: WatchlistItemParsed) => (
            <Card
              key={item.id}
              className="flex items-center justify-between gap-4"
            >
              <div className="flex items-center gap-4 min-w-0 flex-1">
                <span className="text-lg font-bold text-white w-20 flex-shrink-0">
                  {item.ticker}
                </span>
                {editingId === item.id ? (
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <Input
                      value={editNotes}
                      onChange={(e) => setEditNotes(e.target.value)}
                      placeholder="Notes..."
                      className="flex-1"
                      disabled={updateNotesMutation.isPending}
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveNotes(item.id);
                        if (e.key === "Escape") cancelEdit();
                      }}
                    />
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => saveNotes(item.id)}
                      disabled={updateNotesMutation.isPending}
                    >
                      {updateNotesMutation.isPending ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Check className="w-4 h-4" />
                      )}
                    </Button>
                    <Button variant="outline" size="sm" onClick={cancelEdit}>
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                ) : (
                  <span
                    className="text-sm text-slate-400 truncate flex-1 cursor-pointer hover:text-slate-300"
                    onClick={() => startEdit(item)}
                    title="Click to edit notes"
                  >
                    {item.notes || (
                      <span className="italic text-slate-600">
                        No notes – click to add
                      </span>
                    )}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <span className="text-xs text-slate-500 hidden sm:flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" />
                  {new Date(item.created_at).toLocaleDateString()}
                </span>
                {editingId !== item.id && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => startEdit(item)}
                  >
                    <Edit3 className="w-4 h-4" />
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => removeMutation.mutate(item.id)}
                  disabled={
                    removeMutation.isPending &&
                    removeMutation.variables === item.id
                  }
                >
                  {removeMutation.isPending &&
                  removeMutation.variables === item.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4 text-red-400" />
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
