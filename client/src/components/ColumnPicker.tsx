import { SNAPSHOT_FIELDS, PERF_METRICS, FIELD_LABELS } from "../types/api";

interface ColumnPickerProps {
  selectedFields: string[];
  onFieldsChange: (fields: string[]) => void;
  selectedPerfMetrics: string[];
  onPerfMetricsChange: (metrics: string[]) => void;
  showPerf: boolean;
}

export function ColumnPicker({
  selectedFields,
  onFieldsChange,
  selectedPerfMetrics,
  onPerfMetricsChange,
  showPerf,
}: ColumnPickerProps) {
  const toggleField = (field: string) => {
    if (selectedFields.includes(field)) {
      if (selectedFields.length > 1) {
        onFieldsChange(selectedFields.filter((f) => f !== field));
      }
    } else {
      onFieldsChange([...selectedFields, field]);
    }
  };

  const togglePerfMetric = (metric: string) => {
    if (selectedPerfMetrics.includes(metric)) {
      if (selectedPerfMetrics.length > 1) {
        onPerfMetricsChange(selectedPerfMetrics.filter((m) => m !== metric));
      }
    } else {
      onPerfMetricsChange([...selectedPerfMetrics, metric]);
    }
  };

  const selectAllFields = () => {
    onFieldsChange([...SNAPSHOT_FIELDS]);
  };

  const selectAllPerf = () => {
    onPerfMetricsChange([...PERF_METRICS]);
  };

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-white">Snapshot Columns</h3>
        <button
          onClick={selectAllFields}
          className="text-xs text-blue-400 hover:text-blue-300"
        >
          Select All
        </button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
        {SNAPSHOT_FIELDS.map((field) => (
          <label
            key={field}
            className="flex items-center gap-2 text-sm cursor-pointer group"
          >
            <input
              type="checkbox"
              checked={selectedFields.includes(field)}
              onChange={() => toggleField(field)}
              className="w-4 h-4 text-blue-600 bg-slate-700 border-slate-600 rounded focus:ring-blue-500"
            />
            <span className="text-slate-300 group-hover:text-white truncate">
              {FIELD_LABELS[field] || field}
            </span>
          </label>
        ))}
      </div>

      {showPerf && (
        <>
          <div className="flex items-center justify-between mt-5 mb-3">
            <h3 className="text-sm font-semibold text-white">
              Performance Columns
            </h3>
            <button
              onClick={selectAllPerf}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              Select All
            </button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {PERF_METRICS.map((metric) => (
              <label
                key={metric}
                className="flex items-center gap-2 text-sm cursor-pointer group"
              >
                <input
                  type="checkbox"
                  checked={selectedPerfMetrics.includes(metric)}
                  onChange={() => togglePerfMetric(metric)}
                  className="w-4 h-4 text-green-600 bg-slate-700 border-slate-600 rounded focus:ring-green-500"
                />
                <span className="text-slate-300 group-hover:text-white">
                  {FIELD_LABELS[metric] || metric}
                </span>
              </label>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
