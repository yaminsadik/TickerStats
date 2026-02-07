import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Trash2, Eye, Plus, Clock, Tag, Loader2 } from "lucide-react";
import { Button, Card, Alert, Badge } from "../components/ui";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import { RelativeTable } from "../components/RelativeTable";
import {
  fetchSavedAnalyses,
  deleteSavedAnalysis,
  type SavedAnalysis,
} from "../api/userApi";

export default function SavedSearchesPage() {
  const navigate = useNavigate();
  const { authenticatedFetch } = useAuthenticatedFetch();
  const [analyses, setAnalyses] = useState<SavedAnalysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSavedAnalyses(authenticatedFetch);
      setAnalyses(data);
    } catch (err: any) {
      setError(err.message || "Failed to load saved searches");
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
      await deleteSavedAnalysis(authenticatedFetch, id);
      setAnalyses((prev) => prev.filter((a) => a.id !== id));
    } catch (err: any) {
      setError(err.message || "Failed to delete");
    } finally {
      setDeletingId(null);
    }
  };

  const handleLoad = (analysis: SavedAnalysis) => {
    // Navigate to browse page with the saved analysis config pre-loaded
    navigate("/browse", {
      state: {
        savedAnalysis: {
          symbols: analysis.symbols,
          snapshot_fields: analysis.snapshot_fields,
          perf_periods: analysis.perf_periods,
          include_dcf: analysis.include_dcf,
          snapshot_data: analysis.snapshot_data ?? null,
        },
      },
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Saved Searches</h1>
          <p className="text-slate-400 mt-1">
            Your saved comparison configurations
          </p>
        </div>
        <Button onClick={() => navigate("/browse")} size="sm">
          <Plus className="w-4 h-4 mr-2" />
          New Search
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
      ) : analyses.length === 0 ? (
        <Card className="text-center py-16 px-6">
          <div className="w-20 h-20 mx-auto mb-4 bg-slate-800 rounded-full flex items-center justify-center">
            <Search className="w-10 h-10 text-slate-500" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">
            No Saved Searches Yet
          </h3>
          <p className="text-slate-400 mb-6 max-w-sm mx-auto">
            Go to the Browse page, set up a comparison, and click "Save Search"
            to store it here.
          </p>
          <Button onClick={() => navigate("/browse")}>
            <Search className="w-4 h-4 mr-2" />
            Go to Browse
          </Button>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {analyses.map((a) => (
            <Card key={a.id} className="flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-lg font-semibold text-white truncate pr-2">
                    {a.name}
                  </h3>
                  {a.include_dcf && (
                    <Badge variant="info" className="flex-shrink-0">
                      DCF
                    </Badge>
                  )}
                </div>
                {a.description && (
                  <p className="text-sm text-slate-400 mb-3 line-clamp-2">
                    {a.description}
                  </p>
                )}
                {a.snapshot_data ? (
                  <div className="mb-3 max-h-64 overflow-auto border border-slate-800 rounded">
                    <RelativeTable
                      data={a.snapshot_data}
                      visibleFields={
                        a.snapshot_data.requested?.fields?.length
                          ? a.snapshot_data.requested.fields
                          : a.snapshot_fields ?? []
                      }
                      visiblePerfMetrics={
                        a.snapshot_data.requested?.perf?.metrics ?? []
                      }
                      showPerf={!!a.snapshot_data.requested?.perf}
                      showDcf={!!a.snapshot_data.requested?.dcf}
                    />
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {a.symbols.slice(0, 8).map((s) => (
                      <span
                        key={s}
                        className="inline-flex items-center px-2 py-0.5 bg-slate-800 text-slate-300 rounded text-xs font-medium"
                      >
                        <Tag className="w-3 h-3 mr-1 text-slate-500" />
                        {s}
                      </span>
                    ))}
                    {a.symbols.length > 8 && (
                      <span className="text-xs text-slate-500">
                        +{a.symbols.length - 8} more
                      </span>
                    )}
                  </div>
                )}
                <div className="flex items-center text-xs text-slate-500">
                  <Clock className="w-3.5 h-3.5 mr-1" />
                  {new Date(a.created_at).toLocaleDateString()}
                </div>
              </div>
              <div className="flex gap-2 mt-4 pt-3 border-t border-slate-800">
                <Button
                  variant="primary"
                  size="sm"
                  className="flex-1"
                  onClick={() => handleLoad(a)}
                >
                  <Eye className="w-4 h-4 mr-1" />
                  Load
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDelete(a.id)}
                  disabled={deletingId === a.id}
                >
                  {deletingId === a.id ? (
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
