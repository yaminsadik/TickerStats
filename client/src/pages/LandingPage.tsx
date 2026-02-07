import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import {
  ChevronDown,
  CheckCircle,
  TrendingUp,
  FileText,
  Zap,
  Shield,
  Users,
  ExternalLink,
} from "lucide-react";

export default function LandingPage() {
  const navigate = useNavigate();
  const { isAuthenticated, loginWithRedirect } = useAuth0();
  const [activeSection, setActiveSection] = useState("");
  const [isNavSticky, setIsNavSticky] = useState(false);

  // Handle navigation - check auth first
  const handleNavigate = (path: string, isSignup = false) => {
    if (isAuthenticated) {
      navigate(path);
    } else {
      loginWithRedirect({
        authorizationParams: isSignup ? { screen_hint: "signup" } : {},
        appState: {
          returnTo: path,
        },
      });
    }
  };

  useEffect(() => {
    const handleScroll = () => {
      setIsNavSticky(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Top Navigation */}
      <nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          isNavSticky
            ? "bg-slate-950/95 backdrop-blur-sm border-b border-slate-800"
            : "bg-transparent"
        }`}
      >
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-6 h-6 text-blue-500" />
              <span className="text-xl font-bold text-white">TickerStats</span>
            </div>
            <div className="hidden md:flex items-center gap-8">
              <button
                onClick={() => scrollToSection("product")}
                className="text-slate-300 hover:text-white transition-colors text-sm"
              >
                Product
              </button>
              <button
                onClick={() => scrollToSection("workflow")}
                className="text-slate-300 hover:text-white transition-colors text-sm"
              >
                Workflow
              </button>
              <button
                onClick={() => scrollToSection("trust")}
                className="text-slate-300 hover:text-white transition-colors text-sm"
              >
                Trust
              </button>
              <button
                onClick={() => scrollToSection("pricing")}
                className="text-slate-300 hover:text-white transition-colors text-sm"
              >
                Pricing
              </button>
              <button
                onClick={() => scrollToSection("faq")}
                className="text-slate-300 hover:text-white transition-colors text-sm"
              >
                FAQ
              </button>
            </div>
            {isAuthenticated ? (
              <button
                onClick={() => navigate("/deck/new")}
                className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg font-medium transition-colors text-sm"
              >
                Generate a deck
              </button>
            ) : (
              <button
                onClick={() =>
                  loginWithRedirect({
                    authorizationParams: { screen_hint: "signup" },
                    appState: { returnTo: "/deck/new" },
                  })
                }
                className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg font-medium transition-colors text-sm"
              >
                Sign up
              </button>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <h1 className="text-5xl md:text-6xl font-bold text-white mb-6 leading-tight">
                Build pitch-ready decks in minutes.
              </h1>
              <p className="text-xl text-slate-300 mb-8 leading-relaxed">
                TickerStats turns your ticker list into a clean comp table and a
                presentation-ready pitch deck with data-backed valuation and a
                thesis you can defend in Q&A.
              </p>
              <div className="flex flex-wrap gap-4 mb-8">
                <button
                  onClick={() =>
                    isAuthenticated
                      ? navigate("/deck/new")
                      : loginWithRedirect({
                          authorizationParams: { screen_hint: "signup" },
                          appState: { returnTo: "/deck/new" },
                        })
                  }
                  className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 rounded-lg font-semibold transition-colors flex items-center gap-2"
                >
                  Generate a deck
                  <FileText className="w-5 h-5" />
                </button>
                <button
                  onClick={() => handleNavigate("/browse", true)}
                  className="bg-slate-800 hover:bg-slate-700 text-white px-8 py-4 rounded-lg font-semibold transition-colors"
                >
                  Try the comp table
                </button>
              </div>
              <div className="flex flex-wrap gap-3">
                <ProofChip text="Compare up to 100 tickers" />
                <ProofChip text="Deterministic DCF, not guesses" />
                <ProofChip text="Numbers traced to source" />
              </div>
            </div>

            {/* Hero Visual */}
            <div className="relative">
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-2xl">
                <div className="mb-6">
                  <h3 className="text-sm font-semibold text-slate-400 mb-3">
                    COMP TABLE PREVIEW
                  </h3>
                  <div className="bg-slate-950 rounded border border-slate-800 overflow-hidden">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-slate-800/50 border-b border-slate-700">
                          <th className="px-3 py-2 text-left text-slate-300">
                            Symbol
                          </th>
                          <th className="px-3 py-2 text-right text-slate-300">
                            P/E
                          </th>
                          <th className="px-3 py-2 text-right text-slate-300">
                            EV/EBITDA
                          </th>
                          <th className="px-3 py-2 text-right text-slate-300">
                            Margin
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        <tr className="hover:bg-slate-800/30">
                          <td className="px-3 py-2 font-medium text-slate-200">
                            AAPL
                          </td>
                          <td className="px-3 py-2 text-right text-slate-300">
                            29.8
                          </td>
                          <td className="px-3 py-2 text-right text-slate-300">
                            26.8
                          </td>
                          <td className="px-3 py-2 text-right text-emerald-400">
                            27.8%
                          </td>
                        </tr>
                        <tr className="hover:bg-slate-800/30">
                          <td className="px-3 py-2 font-medium text-slate-200">
                            MSFT
                          </td>
                          <td className="px-3 py-2 text-right text-slate-300">
                            21.8
                          </td>
                          <td className="px-3 py-2 text-right text-slate-300">
                            17.6
                          </td>
                          <td className="px-3 py-2 text-right text-emerald-400">
                            39.0%
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-400 mb-3">
                    DECK SECTIONS
                  </h3>
                  <div className="space-y-2">
                    {[
                      "Overview + Catalysts",
                      "SWOT Analysis",
                      "Bull Case",
                      "Bear Case",
                      "Relative Valuation",
                      "DCF Breakdown",
                    ].map((section) => (
                      <div
                        key={section}
                        className="flex items-center gap-2 text-sm text-slate-300"
                      >
                        <CheckCircle className="w-4 h-4 text-blue-500" />
                        {section}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Social Proof Strip */}
      <section className="py-12 border-y border-slate-800 bg-slate-900/30">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid md:grid-cols-2 gap-8">
            <TestimonialCard
              quote="We stopped spending weekends formatting decks. Now we spend time arguing the thesis."
              attribution="Student Investment Fund"
            />
            <TestimonialCard
              quote="The comp table alone saved us hours every week."
              attribution="Student Investment Fund"
            />
          </div>
        </div>
      </section>

      {/* Product Section */}
      <section id="product" className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-4xl font-bold text-white mb-4 text-center">
            Two tools, one platform
          </h2>
          <p className="text-xl text-slate-400 mb-16 text-center max-w-2xl mx-auto">
            Start with comparative analysis or jump straight to deck generation.
          </p>
          <div className="grid md:grid-cols-2 gap-8">
            <FeatureCard
              icon={null}
              title="Browse and Compare"
              features={[
                "Interactive comparison table (up to 100)",
                "Live market metrics from yfinance",
                "Performance windows (1mo to 5y)",
                "Export CSV",
                "Smart signals (absolute vs percentile)",
              ]}
            />
            <FeatureCard
              icon={null}
              title="AI Pitch Deck Generator"
              features={[
                "Company overview, catalysts, SWOT, Porter's, bull and bear cases",
                "Relative valuation peer view",
                "DCF breakdown with assumptions",
                "Pitch-ready structure for weekly meetings and competitions",
                "Regenerate any section",
                "Verification flags for claims",
              ]}
            />
          </div>
        </div>
      </section>

      {/* Workflow Section */}
      <section id="workflow" className="py-20 px-6 bg-slate-900/30">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-4xl font-bold text-white mb-4 text-center">
            Simple workflow
          </h2>
          <p className="text-xl text-slate-400 mb-16 text-center max-w-2xl mx-auto">
            From ticker selection to presentation in three steps.
          </p>
          <div className="grid md:grid-cols-3 gap-8">
            <WorkflowStep
              number={1}
              title="Build your list"
              description="Pick tickers, choose peers"
              icon={<Users className="w-6 h-6" />}
            />
            <WorkflowStep
              number={2}
              title="Generate"
              description="Sections run in parallel, fast"
              icon={<Zap className="w-6 h-6" />}
            />
            <WorkflowStep
              number={3}
              title="Present and iterate"
              description="Regenerate, export, reuse"
              icon={<FileText className="w-6 h-6" />}
            />
          </div>
        </div>
      </section>

      {/* Trust Section */}
      <section id="trust" className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-4xl font-bold text-white mb-4 text-center">
            Built for defendable research
          </h2>
          <p className="text-xl text-slate-400 mb-16 text-center max-w-2xl mx-auto">
            Transparency and accuracy matter when you present to peers and
            professors.
          </p>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            <TrustCard
              icon={null}
              title="Computed vs written"
              description="Deterministic: metrics + DCF computed. LLM: narrative only"
            />
            <TrustCard
              icon={null}
              title="Numbers gate"
              description="Metrics are sourced and timestamped. Hover any metric to see the source and timestamp."
            />
            <TrustCard
              icon={null}
              title="Claim checks"
              description="Flags claims that need verification"
            />
            <TrustCard
              icon={null}
              title="Transparent inputs"
              description="Show DCF assumptions and periods"
            />
          </div>
          <p className="text-xs text-slate-500 mt-8 text-center">
            For research and education. Not investment advice.
          </p>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-20 px-6 bg-slate-900/30">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-4xl font-bold text-white mb-4 text-center">
            Choose your plan
          </h2>
          <p className="text-xl text-slate-400 mb-16 text-center max-w-2xl mx-auto">
            Start free, upgrade as your fund grows.
          </p>
          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <PricingCard
              name="Free"
              price="$0"
              period="forever"
              features={["3 decks/month", "Fast mode", "Basic comparisons"]}
              cta={isAuthenticated ? "Generate a deck" : "Get Started"}
              onClick={() =>
                isAuthenticated
                  ? navigate("/deck/new")
                  : loginWithRedirect({
                      authorizationParams: { screen_hint: "signup" },
                      appState: { returnTo: "/deck/new" },
                    })
              }
            />
            <PricingCard
              name="Pro"
              price="$29"
              period="/month"
              features={[
                "Unlimited decks",
                "DCF valuation",
                "Custom peers",
                "Balanced + Deep modes",
              ]}
              cta={isAuthenticated ? "Generate a deck" : "Start Pro"}
              onClick={() =>
                isAuthenticated
                  ? navigate("/deck/new")
                  : loginWithRedirect({
                      authorizationParams: { screen_hint: "signup" },
                      appState: { returnTo: "/deck/new", plan: "pro" },
                    })
              }
              highlighted
            />
            <PricingCard
              name="Team"
              price="$99"
              period="/month"
              features={[
                "Shared workspace",
                "Collaboration features (roles, shared drafts, templates)",
                "API access",
                "Priority support",
              ]}
              cta="Contact Sales"
              onClick={() => navigate("/contact")}
            />
          </div>
          <p className="text-xs text-slate-500 mt-8 text-center">
            Model names can change. Choose Fast, Balanced, or Deep.
          </p>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-4xl font-bold text-white mb-4">
            Ready for your next pitch?
          </h2>
          <p className="text-xl text-slate-400 mb-8">
            Generate a deck or start with the comp table in under a minute.
          </p>
          <div className="flex flex-wrap gap-4 justify-center">
            <button
              onClick={() => navigate("/deck/new")}
              className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 rounded-lg font-semibold transition-colors inline-flex items-center gap-2"
            >
              Generate a deck
              <FileText className="w-5 h-5" />
            </button>
            <button
              onClick={() => navigate("/browse")}
              className="bg-slate-800 hover:bg-slate-700 text-white px-8 py-4 rounded-lg font-semibold transition-colors"
            >
              Try the comp table
            </button>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section id="faq" className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-4xl font-bold text-white mb-16 text-center">
            Frequently asked questions
          </h2>
          <div className="space-y-6">
            <FAQItem
              question="Where does the data come from?"
              answer="All market data, financials, and metrics come from Yahoo Finance via the yfinance library. Data is timestamped and traceable."
            />
            <FAQItem
              question="What parts are deterministic vs AI-generated?"
              answer="All numbers (metrics, DCF calculations, comparables) are computed deterministically using formulas and market data. AI generates only the narrative text: thesis statements, qualitative analysis, and bullet explanations."
            />
            <FAQItem
              question="Can I choose peer companies?"
              answer="Yes. You can select specific tickers for peer comparison or let the system auto-select based on sector. The comp table supports up to 100 tickers."
            />
            <FAQItem
              question="How fast is generation?"
              answer="Most decks generate in 30-60 seconds. Sections are generated in parallel for speed. Cached data makes subsequent runs even faster."
            />
            <FAQItem
              question="Is this investment advice?"
              answer="No. TickerStats is a research and educational tool. All outputs are for informational purposes only. Always do your own due diligence and consult professionals for investment decisions."
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-slate-800">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-500" />
              <span className="font-semibold text-white">TickerStats</span>
            </div>
            <div className="flex flex-wrap gap-6 text-sm text-slate-400">
              <a href="#" className="hover:text-white transition-colors">
                Terms
              </a>
              <a href="#" className="hover:text-white transition-colors">
                Privacy
              </a>
              <a href="#" className="hover:text-white transition-colors">
                Contact
              </a>
            </div>
            <div className="text-sm text-slate-500">
              © 2026 TickerStats. All rights reserved.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

// Component: ProofChip
function ProofChip({ text }: { text: string }) {
  return (
    <div className="inline-flex items-center px-4 py-2 bg-blue-500/10 border border-blue-500/30 rounded-full text-sm text-blue-300 font-medium">
      {text}
    </div>
  );
}

// Component: TestimonialCard
function TestimonialCard({
  quote,
  attribution,
}: {
  quote: string;
  attribution: string;
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
      <p className="text-slate-300 mb-4 italic">"{quote}"</p>
      <p className="text-sm text-slate-500">{attribution}</p>
    </div>
  );
}

// Component: FeatureCard
function FeatureCard({
  icon,
  title,
  features,
}: {
  icon: React.ReactNode;
  title: string;
  features: string[];
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-8">
      <h3 className="text-2xl font-bold text-white mb-6">{title}</h3>
      <ul className="space-y-3">
        {features.map((feature, idx) => (
          <li key={idx} className="flex items-start gap-3 text-slate-300">
            <span className="text-blue-500 mt-0.5">•</span>
            <span>{feature}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Component: WorkflowStep
function WorkflowStep({
  number,
  title,
  description,
  icon,
}: {
  number: number;
  title: string;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="relative">
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-8">
        <div className="flex items-baseline gap-3 mb-3">
          <span className="text-3xl font-bold text-blue-600">{number}</span>
          <h3 className="text-xl font-bold text-white">{title}</h3>
        </div>
        <p className="text-slate-400 ml-10">{description}</p>
      </div>
    </div>
  );
}

// Component: TrustCard
function TrustCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-sm text-slate-400 leading-relaxed">{description}</p>
    </div>
  );
}

// Component: PricingCard
function PricingCard({
  name,
  price,
  period,
  features,
  cta,
  onClick,
  highlighted = false,
}: {
  name: string;
  price: string;
  period: string;
  features: string[];
  cta: string;
  onClick: () => void;
  highlighted?: boolean;
}) {
  return (
    <div
      className={`rounded-lg p-8 ${
        highlighted
          ? "bg-blue-600 border-2 border-blue-500 shadow-xl scale-105"
          : "bg-slate-900 border border-slate-800"
      }`}
    >
      <h3
        className={`text-xl font-bold mb-2 ${highlighted ? "text-white" : "text-white"}`}
      >
        {name}
      </h3>
      <div className="mb-6">
        <span
          className={`text-4xl font-bold ${highlighted ? "text-white" : "text-white"}`}
        >
          {price}
        </span>
        <span
          className={`text-sm ${highlighted ? "text-blue-100" : "text-slate-400"}`}
        >
          {period}
        </span>
      </div>
      <ul className="space-y-3 mb-8">
        {features.map((feature, idx) => (
          <li
            key={idx}
            className={`flex items-start gap-2 ${highlighted ? "text-blue-50" : "text-slate-300"}`}
          >
            <CheckCircle
              className={`w-5 h-5 flex-shrink-0 mt-0.5 ${highlighted ? "text-blue-200" : "text-blue-500"}`}
            />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
      <button
        onClick={onClick}
        className={`w-full py-3 rounded-lg font-semibold transition-colors ${
          highlighted
            ? "bg-white text-blue-600 hover:bg-blue-50"
            : "bg-slate-800 text-white hover:bg-slate-700"
        }`}
      >
        {cta}
      </button>
    </div>
  );
}

// Component: FAQItem
function FAQItem({ question, answer }: { question: string; answer: string }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-slate-800/50 transition-colors"
      >
        <span className="font-semibold text-white">{question}</span>
        <ChevronDown
          className={`w-5 h-5 text-slate-400 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>
      {isOpen && (
        <div className="px-6 pb-4 text-slate-300 leading-relaxed">{answer}</div>
      )}
    </div>
  );
}
