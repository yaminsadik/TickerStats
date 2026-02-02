import { useState, Fragment } from 'react';
import type { SignalSettings, SignalRule } from '../types/signals';
import { METRIC_CATEGORIES, DEFAULT_SIGNAL_RULES } from '../types/signals';

interface SignalConfigDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  settings: SignalSettings;
  onUpdateRule: (metricKey: string, updates: Partial<SignalRule>) => void;
  onReset: () => void;
}

function RuleEditor({
  metricKey,
  rule,
  globalMode,
  onUpdate,
}: {
  metricKey: string;
  rule: SignalRule;
  globalMode: 'percentile' | 'absolute';
  onUpdate: (updates: Partial<SignalRule>) => void;
}) {
  const isPercentile = globalMode === 'percentile';
  const thresholds = isPercentile ? rule.percentile : rule.absolute;
  const defaultRule = DEFAULT_SIGNAL_RULES[metricKey];

  return (
    <div className="py-3 border-b border-slate-100 last:border-b-0">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={rule.enabled}
              onChange={(e) => onUpdate({ enabled: e.target.checked })}
              className="w-3.5 h-3.5 rounded border-slate-300 text-emerald-500 focus:ring-emerald-500"
            />
            <span className="text-sm font-medium text-slate-800">{rule.label}</span>
          </label>
          <span
            className={`text-xs px-1.5 py-0.5 rounded ${
              rule.direction === 'higher_better'
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-amber-50 text-amber-700'
            }`}
          >
            {rule.direction === 'higher_better' ? '↑ higher better' : '↓ lower better'}
          </span>
        </div>
      </div>

      {rule.enabled && (
        <div className="ml-5 grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Good {isPercentile ? '(≤ percentile)' : '(threshold)'}
            </label>
            <input
              type="number"
              value={thresholds.good}
              onChange={(e) =>
                onUpdate({
                  [globalMode]: { ...thresholds, good: parseFloat(e.target.value) || 0 },
                })
              }
              step={isPercentile ? 5 : 0.1}
              className="w-full px-2 py-1.5 text-sm border border-slate-200 rounded focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
            />
            <span className="text-xs text-slate-400">
              Default: {isPercentile ? defaultRule.percentile.good : defaultRule.absolute.good}
            </span>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Warn {isPercentile ? '(≥ percentile)' : '(threshold)'}
            </label>
            <input
              type="number"
              value={thresholds.warn}
              onChange={(e) =>
                onUpdate({
                  [globalMode]: { ...thresholds, warn: parseFloat(e.target.value) || 0 },
                })
              }
              step={isPercentile ? 5 : 0.1}
              className="w-full px-2 py-1.5 text-sm border border-slate-200 rounded focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
            />
            <span className="text-xs text-slate-400">
              Default: {isPercentile ? defaultRule.percentile.warn : defaultRule.absolute.warn}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SignalConfigDrawer({
  isOpen,
  onClose,
  settings,
  onUpdateRule,
  onReset,
}: SignalConfigDrawerProps) {
  const [expandedCategory, setExpandedCategory] = useState<string | null>('valuation');

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-full max-w-md bg-white shadow-xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Signal Configuration</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Mode: <span className="font-medium">{settings.globalMode}</span> thresholds
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Info Banner */}
        <div className="px-4 py-2 bg-slate-50 border-b border-slate-200 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded bg-emerald-100 border border-emerald-300" />
            Good
          </span>
          <span className="mx-2 text-slate-300">|</span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded bg-amber-100 border border-amber-300" />
            Warn
          </span>
          <span className="mx-2 text-slate-300">|</span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded bg-slate-50 border border-slate-200" />
            Neutral
          </span>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {METRIC_CATEGORIES.map((category) => (
            <Fragment key={category.id}>
              <button
                onClick={() =>
                  setExpandedCategory(expandedCategory === category.id ? null : category.id)
                }
                className="w-full px-4 py-2.5 flex items-center justify-between bg-slate-50 hover:bg-slate-100 transition-colors border-b border-slate-200"
              >
                <span className="text-sm font-medium text-slate-700">{category.label}</span>
                <svg
                  className={`w-4 h-4 text-slate-400 transition-transform ${
                    expandedCategory === category.id ? 'rotate-180' : ''
                  }`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {expandedCategory === category.id && (
                <div className="px-4">
                  {category.metrics.map((metricKey) => {
                    const rule = settings.rules[metricKey];
                    if (!rule) return null;
                    return (
                      <RuleEditor
                        key={metricKey}
                        metricKey={metricKey}
                        rule={rule}
                        globalMode={settings.globalMode}
                        onUpdate={(updates) => onUpdateRule(metricKey, updates)}
                      />
                    );
                  })}
                </div>
              )}
            </Fragment>
          ))}

        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-slate-200 flex justify-between">
          <button
            onClick={onReset}
            className="px-3 py-1.5 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded transition-colors"
          >
            Reset to Defaults
          </button>
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm font-medium text-white bg-emerald-500 hover:bg-emerald-600 rounded transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </>
  );
}
