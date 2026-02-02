import { useState, useMemo } from "react";
import type { RelativeTableResponse, RowData } from "../types/api";
import { FIELD_LABELS, DCF_METRICS } from "../types/api";
import { formatValue, formatTimestamp } from "../utils/formatters";
import type { SignalSettings, SignalLevel } from "../types/signals";
import { computeSignalMap } from "../utils/signals";

interface RelativeTableProps {
  data: RelativeTableResponse;
  visibleFields: string[];
  visiblePerfMetrics: string[];
  showPerf: boolean;
  showDcf?: boolean;
  signalSettings?: SignalSettings;
}

type SortDirection = "asc" | "desc" | null;
type SortConfig = {
  key: string;
  direction: SortDirection;
};

export function RelativeTable({
  data,
  visibleFields,
  visiblePerfMetrics,
  showPerf,
  showDcf,
  signalSettings,
}: RelativeTableProps) {
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: "",
    direction: null,
  });

  const columns = useMemo(() => {
    const cols = visibleFields.filter((f) => data.requested.fields.includes(f));
    if (showPerf && data.requested.perf) {
      const perfCols = visiblePerfMetrics.filter((m) =>
        data.requested.perf?.metrics.includes(m),
      );
      cols.push(...perfCols);
    }
    if (showDcf && data.requested.dcf) {
      cols.push(...DCF_METRICS);
    }
    return cols;
  }, [visibleFields, visiblePerfMetrics, showPerf, showDcf, data.requested]);

  const sortedRows = useMemo(() => {
    if (!sortConfig.key || !sortConfig.direction) {
      return data.rows;
    }

    return [...data.rows].sort((a, b) => {
      let aVal: number | string | null;
      let bVal: number | string | null;

      if (sortConfig.key === "symbol") {
        aVal = a.symbol;
        bVal = b.symbol;
      } else if (a.snapshot[sortConfig.key] !== undefined) {
        aVal = a.snapshot[sortConfig.key];
        bVal = b.snapshot[sortConfig.key];
      } else if (a.performance && a.performance[sortConfig.key] !== undefined) {
        aVal = a.performance[sortConfig.key];
        bVal = b.performance?.[sortConfig.key] ?? null;
      } else if (a.dcf && a.dcf[sortConfig.key] !== undefined) {
        aVal = a.dcf[sortConfig.key];
        bVal = b.dcf?.[sortConfig.key] ?? null;
      } else {
        return 0;
      }

      // Handle nulls - push to end
      if (aVal === null && bVal === null) return 0;
      if (aVal === null) return 1;
      if (bVal === null) return -1;

      // Compare
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortConfig.direction === "asc"
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      const numA = aVal as number;
      const numB = bVal as number;
      return sortConfig.direction === "asc" ? numA - numB : numB - numA;
    });
  }, [data.rows, sortConfig]);

  const handleSort = (key: string) => {
    setSortConfig((prev) => {
      if (prev.key !== key) {
        return { key, direction: "desc" };
      }
      if (prev.direction === "desc") {
        return { key, direction: "asc" };
      }
      if (prev.direction === "asc") {
        return { key: "", direction: null };
      }
      return { key, direction: "desc" };
    });
  };

  const getSortIcon = (key: string) => {
    if (sortConfig.key !== key) {
      return (
        <svg
          className="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
          />
        </svg>
      );
    }

    if (sortConfig.direction === "asc") {
      return (
        <svg
          className="w-4 h-4 text-blue-600"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 15l7-7 7 7"
          />
        </svg>
      );
    }

    return (
      <svg
        className="w-4 h-4 text-blue-600"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M19 9l-7 7-7-7"
        />
      </svg>
    );
  };

  const getValue = (row: RowData, col: string): number | null => {
    if (row.snapshot[col] !== undefined) {
      return row.snapshot[col];
    }
    if (row.performance && row.performance[col] !== undefined) {
      return row.performance[col];
    }
    if (row.dcf && row.dcf[col] !== undefined) {
      return row.dcf[col];
    }
    return null;
  };

  const isFieldColumn = (col: string): boolean => {
    return visibleFields.includes(col);
  };

  const isDcfColumn = (col: string): boolean => {
    return (DCF_METRICS as readonly string[]).includes(col);
  };

  // Performance metrics should not have signals applied
  const PERF_METRICS = ["return", "volatility", "maxDrawdown"];

  // Compute signal levels for snapshot columns only (not performance)
  const signalMap = useMemo(() => {
    if (!signalSettings?.enabled) return null;
    const snapshotColumns = columns.filter(
      (col) => !PERF_METRICS.includes(col),
    );
    return computeSignalMap(data.rows, snapshotColumns, signalSettings);
  }, [data.rows, columns, signalSettings]);

  const getSignalClass = (level: SignalLevel | undefined): string => {
    if (!level) return "";
    switch (level) {
      case "good":
        return "bg-emerald-50 border-l-2 border-l-emerald-400";
      case "warn":
        return "bg-amber-50 border-l-2 border-l-amber-400";
      default:
        return "";
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
      {/* Header with timestamp */}
      <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <span className="text-xs text-gray-500">
          Data as of:{" "}
          <span className="font-medium">{formatTimestamp(data.asOf)}</span>
        </span>
        <span className="text-xs text-gray-500">
          {data.rows.length} ticker{data.rows.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Table container with scroll */}
      <div className="overflow-auto max-h-[600px]">
        <table className="w-full text-sm">
          <thead className="sticky-header">
            <tr className="bg-gray-50 border-b border-gray-200">
              {/* Symbol column - sticky */}
              <th
                onClick={() => handleSort("symbol")}
                className="sticky-col bg-gray-50 px-4 py-3 text-left font-semibold text-gray-900 cursor-pointer group border-r border-gray-200"
              >
                <div className="flex items-center gap-1">
                  Symbol
                  {getSortIcon("symbol")}
                </div>
              </th>

              {/* Data columns */}
              {columns.map((col) => (
                <th
                  key={col}
                  onClick={() => handleSort(col)}
                  className={`px-4 py-3 text-right font-semibold cursor-pointer group whitespace-nowrap ${
                    isDcfColumn(col)
                      ? "text-purple-800 bg-purple-50"
                      : isFieldColumn(col)
                        ? "text-gray-900"
                        : "text-green-800 bg-green-50"
                  }`}
                >
                  <div className="flex items-center justify-end gap-1">
                    {FIELD_LABELS[col] || col}
                    {getSortIcon(col)}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sortedRows.map((row) => (
              <tr
                key={row.symbol}
                className="hover:bg-gray-50 transition-colors"
              >
                {/* Symbol cell - sticky */}
                <td className="sticky-col bg-white px-4 py-3 font-medium text-gray-900 border-r border-gray-100">
                  <div className="flex items-center gap-2">
                    {row.symbol}
                    {row.error && (
                      <span
                        title={row.error}
                        className="inline-flex items-center justify-center w-5 h-5 text-xs bg-amber-100 text-amber-700 rounded-full cursor-help"
                      >
                        !
                      </span>
                    )}
                  </div>
                </td>

                {/* Data cells */}
                {columns.map((col) => {
                  const value = getValue(row, col);
                  const unit = data.units[col];
                  const isMissing =
                    row.missingFields?.includes(col) ||
                    row.missingPerf?.includes(col);
                  const signalLevel = signalMap?.get(`${row.symbol}:${col}`);
                  const isDcf = isDcfColumn(col);

                  // Special styling for DCF upside - color based on value
                  const dcfUpsideColor =
                    col === "dcfUpside" && value !== null
                      ? value >= 0
                        ? "text-emerald-600 font-medium"
                        : "text-red-600 font-medium"
                      : "";

                  return (
                    <td
                      key={col}
                      className={`px-4 py-3 text-right tabular-nums font-mono text-sm transition-colors ${
                        isDcf
                          ? `text-purple-700 bg-purple-50/30 ${dcfUpsideColor}`
                          : isFieldColumn(col)
                            ? "text-gray-700"
                            : "text-green-700 bg-green-50/30"
                      } ${isMissing ? "text-gray-400" : ""} ${getSignalClass(signalLevel)}`}
                    >
                      {formatValue(value, unit, col)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
