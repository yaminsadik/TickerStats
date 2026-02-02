import Modal from "./ui/Modal";

interface PerformanceExplainerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function PerformanceExplainerModal({
  isOpen,
  onClose,
}: PerformanceExplainerModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Performance Metrics Explained"
      subtitle="Understanding return, volatility, and risk metrics"
      size="lg"
    >
      <div className="space-y-6 text-gray-300">
        {/* Overview */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-2">
            What are Performance Metrics?
          </h3>
          <p className="text-sm leading-relaxed">
            Performance metrics measure how a stock has performed over a
            specific time period, including returns and risk characteristics.
            These are backward-looking indicators based on historical price
            data.
          </p>
        </section>

        {/* Return */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-3">
            Total Return
          </h3>
          <div className="bg-slate-800 rounded-lg p-4 space-y-3">
            <p className="text-sm">
              Total return measures the percentage change in stock price over
              the selected period, including dividends and capital gains.
            </p>
            <code className="block bg-slate-900 p-3 rounded text-xs text-green-400">
              Return % = ((Ending Price - Starting Price) / Starting Price) ×
              100
            </code>
            <div className="space-y-2 text-sm">
              <div className="flex items-start gap-2">
                <span className="text-green-400 font-bold">+25%</span>
                <span>→ Stock gained 25% over the period</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-red-400 font-bold">-15%</span>
                <span>→ Stock lost 15% over the period</span>
              </div>
            </div>
          </div>
        </section>

        {/* Volatility */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-3">
            Volatility (Standard Deviation)
          </h3>
          <div className="bg-slate-800 rounded-lg p-4 space-y-3">
            <p className="text-sm">
              Volatility measures the degree of price fluctuation. Higher
              volatility means larger price swings (higher risk and potentially
              higher reward).
            </p>
            <code className="block bg-slate-900 p-3 rounded text-xs text-green-400 whitespace-pre">
              {`1. Calculate daily returns
2. Find standard deviation of returns
3. Annualize: σ_annual = σ_daily × √252

Volatility % = Standard Deviation × 100`}
            </code>
            <div className="space-y-2 text-sm">
              <div className="flex items-start gap-2">
                <span className="text-blue-400 font-bold">15%</span>
                <span>→ Low volatility (stable, less risky)</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-yellow-400 font-bold">35%</span>
                <span>→ Moderate volatility</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-red-400 font-bold">60%+</span>
                <span>→ High volatility (unpredictable, risky)</span>
              </div>
            </div>
            <p className="text-xs text-gray-400">
              68% of returns fall within ±1 standard deviation, 95% within ±2σ
            </p>
          </div>
        </section>

        {/* Max Drawdown */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-3">
            Maximum Drawdown
          </h3>
          <div className="bg-slate-800 rounded-lg p-4 space-y-3">
            <p className="text-sm">
              Maximum drawdown measures the largest peak-to-trough decline
              during the period. It shows the worst-case scenario an investor
              would have experienced.
            </p>
            <code className="block bg-slate-900 p-3 rounded text-xs text-green-400 whitespace-pre">
              {`1. Track cumulative returns over period
2. Find highest peak price
3. Find lowest trough after that peak
4. Max Drawdown = (Trough - Peak) / Peak × 100`}
            </code>
            <div className="mt-3 bg-slate-900 rounded p-3 text-xs">
              <p className="text-gray-400 mb-2">Example:</p>
              <ul className="space-y-1 text-gray-300">
                <li>• Stock peaks at $100 (Jan 15)</li>
                <li>• Stock drops to $70 (Mar 1)</li>
                <li>
                  • Max Drawdown = (70 - 100) / 100 ={" "}
                  <span className="text-red-400 font-bold">-30%</span>
                </li>
              </ul>
            </div>
            <div className="space-y-2 text-sm mt-3">
              <div className="flex items-start gap-2">
                <span className="text-green-400 font-bold">-10%</span>
                <span>→ Small drawdown (resilient)</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-yellow-400 font-bold">-25%</span>
                <span>→ Moderate drawdown</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-red-400 font-bold">-50%+</span>
                <span>→ Severe drawdown (high risk)</span>
              </div>
            </div>
          </div>
        </section>

        {/* Time Periods */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-3">
            Time Periods
          </h3>
          <div className="bg-slate-800 rounded-lg p-4">
            <p className="text-sm mb-3">
              Performance can be calculated over different periods:
            </p>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="font-medium text-white">1mo, 3mo, 6mo:</span>{" "}
                Short-term
              </div>
              <div>
                <span className="font-medium text-white">ytd:</span>{" "}
                Year-to-date
              </div>
              <div>
                <span className="font-medium text-white">1y, 2y:</span>{" "}
                Medium-term
              </div>
              <div>
                <span className="font-medium text-white">5y, 10y:</span>{" "}
                Long-term
              </div>
              <div className="col-span-2">
                <span className="font-medium text-white">max:</span> Since
                inception or earliest available data
              </div>
            </div>
          </div>
        </section>

        {/* Use Cases */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-2">
            How to Use These Metrics
          </h3>
          <ul className="space-y-2 text-sm list-disc list-inside">
            <li>
              <strong className="text-white">Return:</strong> Compare absolute
              performance across stocks
            </li>
            <li>
              <strong className="text-white">Volatility:</strong> Assess risk
              tolerance and price stability
            </li>
            <li>
              <strong className="text-white">Max Drawdown:</strong> Understand
              worst-case scenario and recovery ability
            </li>
            <li>
              <strong className="text-white">Combined:</strong> Evaluate
              risk-adjusted returns (higher return with lower volatility is
              ideal)
            </li>
          </ul>
        </section>

        {/* Limitations */}
        <section className="bg-amber-900/20 border border-amber-700/50 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-amber-400 mb-2">
            Important Notes
          </h3>
          <ul className="space-y-1 text-sm list-disc list-inside text-amber-200/90">
            <li>Past performance does not guarantee future results</li>
            <li>Performance metrics are backward-looking only</li>
            <li>Different time periods can show very different results</li>
            <li>Market conditions and company fundamentals change over time</li>
          </ul>
        </section>
      </div>
    </Modal>
  );
}
