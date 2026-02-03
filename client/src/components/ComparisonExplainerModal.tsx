import Modal from "./ui/Modal";

interface ComparisonExplainerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ComparisonExplainerModal({
  isOpen,
  onClose,
}: ComparisonExplainerModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Comparison Modes Explained">
      <div className="space-y-6 text-sm text-slate-200">
        {/* Introduction */}
        <p className="text-white font-medium">
          Choose how to evaluate stock metrics against the group of stocks
          you're comparing.
        </p>

        {/* Percentile Mode */}
        <div className="space-y-3">
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <span className="w-2 h-2 bg-emerald-500 rounded-full" />
            Percentile Mode
          </h3>
          <p>
            Compares each stock's metric to the <strong>distribution</strong> of
            values across all stocks in your selection.
          </p>
          <div className="bg-emerald-900/20 border border-emerald-700/60 rounded-lg p-3 space-y-2">
            <p className="font-medium text-emerald-200">How it works:</p>
            <ul className="space-y-1 text-emerald-100 ml-4 list-disc">
              <li>Ranks all stocks by the metric value</li>
              <li>Calculates where each stock falls (0-100 percentile)</li>
              <li>Compares against percentile thresholds you set</li>
            </ul>
          </div>
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-3">
            <p className="font-medium text-white mb-1">Example:</p>
            <p className="text-slate-200">
              If you set P/E ratio "Good" at ≤25th percentile, stocks in the
              bottom 25% (lowest P/E ratios) get a green signal. If a stock is
              at the 80th percentile, it has a higher P/E than 80% of other
              stocks.
            </p>
          </div>
          <p className="text-slate-300 italic">
            ✓ Best when: Comparing relative performance within a specific group
          </p>
        </div>

        {/* Absolute Mode */}
        <div className="space-y-3">
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <span className="w-2 h-2 bg-blue-500 rounded-full" />
            Absolute Mode
          </h3>
          <p>
            Compares each stock's metric against{" "}
            <strong>fixed numeric thresholds</strong> regardless of other
            stocks.
          </p>
          <div className="bg-blue-900/20 border border-blue-700/60 rounded-lg p-3 space-y-2">
            <p className="font-medium text-blue-200">How it works:</p>
            <ul className="space-y-1 text-blue-100 ml-4 list-disc">
              <li>Uses the actual metric values directly</li>
              <li>Compares against fixed numbers you define</li>
              <li>Independent of other stocks in the comparison</li>
            </ul>
          </div>
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-3">
            <p className="font-medium text-white mb-1">Example:</p>
            <p className="text-slate-200">
              If you set P/E ratio "Good" at ≤15, any stock with P/E ratio of 15
              or below gets a green signal, regardless of what other stocks' P/E
              ratios are.
            </p>
          </div>
          <p className="text-slate-300 italic">
            ✓ Best when: Using industry standards or universal benchmarks
          </p>
        </div>

        {/* Quick Comparison */}
        <div className="border border-slate-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-800">
              <tr>
                <th className="px-3 py-2 text-left font-semibold text-white">
                  Aspect
                </th>
                <th className="px-3 py-2 text-left font-semibold text-emerald-200">
                  Percentile
                </th>
                <th className="px-3 py-2 text-left font-semibold text-blue-200">
                  Absolute
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              <tr>
                <td className="px-3 py-2 font-medium text-white">Basis</td>
                <td className="px-3 py-2 text-slate-200">Relative rank</td>
                <td className="px-3 py-2 text-slate-200">Fixed values</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-medium text-white">
                  Changes with
                </td>
                <td className="px-3 py-2 text-slate-200">Stock selection</td>
                <td className="px-3 py-2 text-slate-200">Never (static)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-medium text-white">Use case</td>
                <td className="px-3 py-2 text-slate-200">Best in group</td>
                <td className="px-3 py-2 text-slate-200">Meet standards</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="bg-amber-900/20 border border-amber-700/60 rounded-lg p-3">
          <p className="text-xs text-amber-100">
            <strong>💡 Tip:</strong> You can configure custom thresholds for
            each metric by clicking the "Configure" button next to the mode
            selector.
          </p>
        </div>
      </div>
    </Modal>
  );
}
