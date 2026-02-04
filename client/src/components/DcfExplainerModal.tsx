import Modal from "./ui/Modal";

interface DcfExplainerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function DcfExplainerModal({ isOpen, onClose }: DcfExplainerModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="How DCF Target Price is Calculated"
      subtitle="Deterministic valuation using yfinance data + your assumptions"
      size="lg"
    >
      <div className="p-6 space-y-6 text-gray-300">
        {/* Overview */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-2">
            Overview
          </h3>
          <p className="text-sm leading-relaxed">
            This DCF (Discounted Cash Flow) model computes an intrinsic value
            by forecasting future free cash flows and discounting them to present
            value. All numeric inputs come from yfinance data; NO LLM-generated
            numbers are used in the calculation.
          </p>
        </section>

        {/* Calculation Steps */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-3">
            Step-by-Step Formulas
          </h3>
          <div className="space-y-4">
            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-blue-400 mb-2">
                1. Forecast Free Cash Flow (FCF)
              </h4>
              <code className="block bg-slate-900 p-3 rounded text-sm text-green-400 font-mono">
                FCF_t = FCF_0 × (1 + growth)^t
              </code>
              <p className="text-xs text-gray-400 mt-2">
                FCF_0 is base FCF from yfinance, growth is your FCF growth rate assumption, t is year 1 to N.
              </p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-blue-400 mb-2">
                2. Discount Each Year's FCF
              </h4>
              <code className="block bg-slate-900 p-3 rounded text-sm text-green-400 font-mono">
                PV_FCF_t = FCF_t / (1 + WACC)^t
              </code>
              <p className="text-xs text-gray-400 mt-2">
                Each year's FCF is discounted to present value using your WACC assumption.
              </p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-blue-400 mb-2">
                3. Calculate Terminal Value
              </h4>
              <code className="block bg-slate-900 p-3 rounded text-sm text-green-400 font-mono whitespace-pre-wrap">
{`TV_N = FCF_(N+1) / (WACC - g)
FCF_(N+1) = FCF_N × (1 + g)`}
              </code>
              <p className="text-xs text-gray-400 mt-2">
                Terminal value represents all cash flows beyond year N, assuming perpetual growth at rate g.
                Note: g must be less than WACC.
              </p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-blue-400 mb-2">
                4. Discount Terminal Value
              </h4>
              <code className="block bg-slate-900 p-3 rounded text-sm text-green-400 font-mono">
                PV_TV = TV_N / (1 + WACC)^N
              </code>
            </div>

            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-blue-400 mb-2">
                5. Enterprise Value
              </h4>
              <code className="block bg-slate-900 p-3 rounded text-sm text-green-400 font-mono">
                EV = Σ PV_FCF_t + PV_TV
              </code>
              <p className="text-xs text-gray-400 mt-2">
                Sum of all discounted FCFs plus the discounted terminal value.
              </p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-blue-400 mb-2">
                6. Equity Value
              </h4>
              <code className="block bg-slate-900 p-3 rounded text-sm text-green-400 font-mono">
                Equity = EV + Cash − Debt
              </code>
              <p className="text-xs text-gray-400 mt-2">
                Add cash (belongs to equity holders), subtract debt (claims on enterprise).
              </p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-blue-400 mb-2">
                7. Target Price per Share
              </h4>
              <code className="block bg-slate-900 p-3 rounded text-sm text-green-400 font-mono">
                TargetPrice = Equity / SharesOutstanding
              </code>
            </div>

            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-blue-400 mb-2">
                8. Upside Calculation
              </h4>
              <code className="block bg-slate-900 p-3 rounded text-sm text-green-400 font-mono">
                Upside% = (TargetPrice / MarketPrice) − 1
              </code>
              <div className="mt-3 space-y-1 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-green-400 font-bold">+30%</span>
                  <span className="text-gray-400">→ Stock undervalued by 30%</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-red-400 font-bold">−20%</span>
                  <span className="text-gray-400">→ Stock overvalued by 20%</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Data Sources */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-3">
            Data Sources (yfinance)
          </h3>
          <div className="bg-slate-800 rounded-lg p-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left py-2 text-slate-400 font-medium">Input</th>
                  <th className="text-left py-2 text-slate-400 font-medium">yfinance Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                <tr>
                  <td className="py-2">Market Price</td>
                  <td className="py-2 text-slate-400 font-mono text-xs">info.currentPrice / history</td>
                </tr>
                <tr>
                  <td className="py-2">Shares Outstanding</td>
                  <td className="py-2 text-slate-400 font-mono text-xs">info.sharesOutstanding</td>
                </tr>
                <tr>
                  <td className="py-2">Cash</td>
                  <td className="py-2 text-slate-400 font-mono text-xs">balance_sheet / info.totalCash</td>
                </tr>
                <tr>
                  <td className="py-2">Debt</td>
                  <td className="py-2 text-slate-400 font-mono text-xs">balance_sheet / info.totalDebt</td>
                </tr>
                <tr>
                  <td className="py-2">FCF (Base)</td>
                  <td className="py-2 text-slate-400 font-mono text-xs">cashflow: Operating CF − CapEx</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Important Note */}
        <section className="bg-amber-900/30 border border-amber-700 rounded-lg p-4">
          <h4 className="text-sm font-medium text-amber-400 mb-2">
            Important Note
          </h4>
          <p className="text-xs text-slate-300 leading-relaxed">
            All numbers are computed from yfinance data plus your assumptions.
            If yfinance is missing a value (shown as "manual required" in sources),
            you must enter it manually. The calculation will not proceed with
            missing required inputs to avoid producing misleading valuations.
          </p>
        </section>
      </div>
    </Modal>
  );
}
