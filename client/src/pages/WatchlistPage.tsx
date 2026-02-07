import { useState, useEffect, useCallback } from "react";
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
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import {
  fetchWatchlist,
  addToWatchlist,
  updateWatchlistNotes,
  removeFromWatchlist,
  type WatchlistItem,
} from "../api/userApi";

export default function WatchlistPage() {
  const { authenticatedFetch } = useAuthenticatedFetch();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add form
  const [newTicker, setNewTicker] = useState("");
  const [newNotes, setNewNotes] = useState("");
  const [adding, setAdding] = useState(false);

  // Inline edit
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNotes, setEditNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);

  // Deleting
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWatchlist(authenticatedFetch);
      setItems(data);
    } catch (err: any) {
      setError(err.message || "Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  }, [authenticatedFetch]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTicker.trim()) return;
    setAdding(true);
    setError(null);
    try {
      const item = await addToWatchlist(
        authenticatedFetch,
        newTicker.trim(),
        newNotes.trim() || undefined,
      );
      setItems((prev) => [item, ...prev]);
      setNewTicker("");
      setNewNotes("");
    } catch (err: any) {
      setError(err.message || "Failed to add ticker");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    setDeletingId(id);
    try {
      await removeFromWatchlist(authenticatedFetch, id);
      setItems((prev) => prev.filter((i) => i.id !== id));
    } catch (err: any) {
      setError(err.message || "Failed to remove");
    } finally {
      setDeletingId(null);
    }
  };

  const startEdit = (item: WatchlistItem) => {
    setEditingId(item.id);
    setEditNotes(item.notes || "");
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditNotes("");
  };

  const saveNotes = async (id: number) => {
    setSavingNotes(true);
    try {
      const updated = await updateWatchlistNotes(
        authenticatedFetch,
        id,
        editNotes.trim() || null,
      );
      setItems((prev) => prev.map((i) => (i.id === id ? updated : i)));
      setEditingId(null);
    } catch (err: any) {
      setError(err.message || "Failed to update notes");
    } finally {
      setSavingNotes(false);
    }
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
            disabled={adding}
          />
          <Input
            placeholder="Notes (optional)"
            value={newNotes}
            onChange={(e) => setNewNotes(e.target.value)}
            className="flex-1"
            disabled={adding}
          />
          <Button type="submit" disabled={adding || !newTicker.trim()}>
            {adding ? (
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
      ) : items.length === 0 ? (
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
          {items.map((item) => (
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
                      disabled={savingNotes}
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
                      disabled={savingNotes}
                    >
                      {savingNotes ? (
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
                  onClick={() => handleDelete(item.id)}
                  disabled={deletingId === item.id}
                >
                  {deletingId === item.id ? (
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
