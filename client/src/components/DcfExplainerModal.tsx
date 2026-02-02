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
      title="DCF Valuation Explained"
      subtitle="Understanding how intrinsic value is calculated"
      size="lg"
    >
      <div className="space-y-6 text-gray-300">
        {/* Overview */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-2">
            What is DCF?
          </h3>
          <p className="text-sm leading-relaxed">
            Discounted Cash Flow (DCF) is a valuation method that estimates the
            intrinsic value of a company based on its projected future cash
            flows, discounted back to present value.
          </p>
        </section>

        {/* Calculation Steps */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-3">
            Calculation Steps
          </h3>
          <div className="space-y-4">
            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-white mb-2">
                1. Get Free Cash Flow (FCF)
              </h4>
              <p className="text-sm mb-2">
                Starting point from company's most recent financials:
              </p>
              <code className="block bg-slate-900 p-3 rounded text-xs text-green-400">
                FCF = Operating Cash Flow - Capital Expenditures
              </code>
            </div>

            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-white mb-2">
                2. Project Future Cash Flows (5 years)
              </h4>
              <p className="text-sm mb-2">
                Grow FCF based on historical revenue growth, with decay:
              </p>
              <code className="block bg-slate-900 p-3 rounded text-xs text-green-400 whitespace-pre">
                {`Year 1 FCF = Current FCF × (1 + growth_rate)
Year 2 FCF = Year 1 FCF × (1 + decayed_growth)
...
Year 5 FCF = Year 4 FCF × (1 + terminal_growth)`}
              </code>
              <p className="text-xs text-gray-400 mt-2">
                Growth decays from current rate to 2.5% terminal rate
              </p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-white mb-2">
                3. Discount to Present Value
              </h4>
              <p className="text-sm mb-2">
                Apply WACC (Weighted Average Cost of Capital) discount:
              </p>
              <code className="block bg-slate-900 p-3 rounded text-xs text-green-400 whitespace-pre">
                {`PV of Year N = FCF_N / (1 + WACC)^N

PV of Projected FCF = Σ (each year's PV)`}
              </code>
              <p className="text-xs text-gray-400 mt-2">
                Default WACC: 9% (cost of capital)
              </p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-white mb-2">
                4. Calculate Terminal Value
              </h4>
              <p className="text-sm mb-2">
                Value beyond Year 5 using Gordon Growth Model:
              </p>
              <code className="block bg-slate-900 p-3 rounded text-xs text-green-400 whitespace-pre">
                {`Terminal Value = Year 5 FCF × (1 + g) / (WACC - g)

PV of Terminal = Terminal Value / (1 + WACC)^5`}
              </code>
              <p className="text-xs text-gray-400 mt-2">
                g = 2.5% perpetual growth rate
              </p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-white mb-2">
                5. Enterprise to Equity Value
              </h4>
              <p className="text-sm mb-2">Adjust for debt and cash:</p>
              <code className="block bg-slate-900 p-3 rounded text-xs text-green-400 whitespace-pre">
                {`Enterprise Value = PV of Projected FCF + PV of Terminal

Equity Value = Enterprise Value - Total Debt + Cash`}
              </code>
            </div>

            <div className="bg-slate-800 rounded-lg p-4">
              <h4 className="font-medium text-white mb-2">
                6. Per Share Value
              </h4>
              <code className="block bg-slate-900 p-3 rounded text-xs text-green-400">
                DCF Price = Equity Value / Shares Outstanding
              </code>
            </div>
          </div>
        </section>

        {/* Upside Calculation */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-3">
            DCF Upside Calculation
          </h3>
          <div className="bg-slate-800 rounded-lg p-4">
            <p className="text-sm mb-3">
              Upside represents the potential return from current price to fair
              value:
            </p>
            <code className="block bg-slate-900 p-3 rounded text-xs text-green-400">
              Upside % = (DCF Price / Current Price - 1) × 100
            </code>
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex items-start gap-2">
                <span className="text-green-400 font-bold">+30%</span>
                <span>→ Stock is undervalued by 30%</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-red-400 font-bold">-40%</span>
                <span>
                  → Stock is overvalued; would need to drop 40% to reach fair
                  value
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Key Assumptions */}
        <section>
          <h3 className="text-lg font-semibold text-white mb-2">
            Key Assumptions
          </h3>
          <ul className="space-y-2 text-sm list-disc list-inside">
            <li>WACC (Discount Rate): 9%</li>
            <li>Terminal Growth Rate: 2.5%</li>
            <li>Projection Period: 5 years</li>
            <li>Growth rate capped between -10% and 30%</li>
            <li>Uses historical revenue growth or defaults to 5%</li>
          </ul>
        </section>

        {/* Limitations */}
        <section className="bg-amber-900/20 border border-amber-700/50 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-amber-400 mb-2">
            Limitations
          </h3>
          <ul className="space-y-1 text-sm list-disc list-inside text-amber-200/90">
            <li>DCF is highly sensitive to assumptions (growth rates, WACC)</li>
            <li>Future cash flows are inherently uncertain</li>
            <li>Model uses simplified assumptions for all companies</li>
            <li>Should be one of multiple valuation methods used</li>
          </ul>
        </section>
      </div>
    </Modal>
  );
}
