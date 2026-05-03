import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { motion, useReducedMotion } from "framer-motion";
import {
  ChevronDown,
  CheckCircle,
  TrendingUp,
  ArrowRight,
  Menu,
  X,
  Lock,
  Shield,
  Clock,
  Eye,
  Flag,
  Search,
  Zap,
  Repeat,
  Users,
  Trophy,
  GraduationCap,
} from "lucide-react";
import InteractiveHero from "./InteractiveHero";
import InteractiveCompDemo from "./InteractiveCompDemo";
import InteractiveDeckDemo from "./InteractiveDeckDemo";
import PricingCalculator from "./PricingCalculator";
import HeroPipeline from "../../components/hero/HeroPipeline";
import { TIERS, MODELS } from "./landingData";
import { useProfileQuery } from "../../queries/useProfileQuery";
import { useSubscriptionMutations } from "../../queries/useSubscriptionMutations";

// ─── Scroll-reveal hook ─────────────────────────────────────────────────────

function useScrollReveal<T extends HTMLElement>(threshold = 0.12) {
  const ref = useRef<T>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (prefersReduced) {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);

  return { ref, visible };
}

// ─── Nav sections ───────────────────────────────────────────────────────────

const NAV_SECTIONS = [
  { id: "demos", label: "Product" },
  { id: "trust", label: "Trust" },
  { id: "pricing", label: "Pricing" },
  { id: "faq", label: "FAQ" },
] as const;

// ─── Landing page ───────────────────────────────────────────────────────────

export default function LandingPage() {
  const navigate = useNavigate();
  const { isAuthenticated, loginWithRedirect } = useAuth0();
  const { profile, loading: profileLoading } = useProfileQuery();
  const { createCheckout, isCreatingCheckout } = useSubscriptionMutations();
  const prefersReduced = useReducedMotion() ?? false;

  // ── Scroll spy ──
  const [activeSection, setActiveSection] = useState("");
  const [isNavSticky, setIsNavSticky] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsNavSticky(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Scroll spy via IntersectionObserver
  useEffect(() => {
    const ids = NAV_SECTIONS.map((s) => s.id);
    const observers: IntersectionObserver[] = [];

    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            setActiveSection(id);
          }
        },
        { rootMargin: "-40% 0px -50% 0px" },
      );
      observer.observe(el);
      observers.push(observer);
    });

    return () => observers.forEach((o) => o.disconnect());
  }, []);

  const scrollToSection = useCallback((id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
    setMobileMenuOpen(false);
  }, []);

  // ── CTA handlers ──
  const handlePrimaryCTA = useCallback(() => {
    if (isAuthenticated) {
      navigate("/browse");
    } else {
      loginWithRedirect({
        authorizationParams: { screen_hint: "signup" },
        appState: { returnTo: "/browse" },
      });
    }
  }, [isAuthenticated, navigate, loginWithRedirect]);

  const primaryCTALabel = isAuthenticated ? "Go to app" : "Sign up free";
  const hasPaidExportAccess = Boolean(profile?.can_export);
  const isResolvingTier = isAuthenticated && profileLoading;
  const exportCTALabel = isCreatingCheckout
    ? "Redirecting..."
    : !isAuthenticated
      ? "Sign up to export"
      : hasPaidExportAccess
        ? "Go to app"
        : "Buy export credit";

  const handleExportCTA = useCallback(() => {
    if (isResolvingTier || isCreatingCheckout) return;

    if (!isAuthenticated) {
      loginWithRedirect({
        authorizationParams: { screen_hint: "signup" },
        appState: { returnTo: "/profile" },
      });
      return;
    }

    if (hasPaidExportAccess) {
      navigate("/browse");
      return;
    }

    createCheckout("deck_export");
  }, [
    createCheckout,
    hasPaidExportAccess,
    isAuthenticated,
    isCreatingCheckout,
    isResolvingTier,
    loginWithRedirect,
    navigate,
  ]);

  // ── Scroll reveal refs ──
  const demos = useScrollReveal<HTMLElement>();
  const trust = useScrollReveal<HTMLElement>();
  const pricing = useScrollReveal<HTMLElement>();
  const faq = useScrollReveal<HTMLElement>();
  const cta = useScrollReveal<HTMLElement>();
  const badgeDelay = prefersReduced ? 0 : 0.04;
  const headlineDelay = prefersReduced ? 0 : 0.02;
  const subtextDelay = prefersReduced ? 0 : 0.1;
  const primaryButtonDelay = prefersReduced ? 0 : 0.24;
  const secondaryButtonDelay = prefersReduced ? 0 : 0.34;
  const trustDelay = prefersReduced ? 0 : 0.46;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Skip to content */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-[100] focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded-lg"
      >
        Skip to content
      </a>

      {/* ── Navigation ───────────────────────────────────────────────── */}
      <nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          isNavSticky || mobileMenuOpen
            ? "bg-slate-950/95 backdrop-blur-sm border-b border-slate-800 shadow-lg shadow-black/20"
            : "bg-transparent"
        }`}
        aria-label="Main navigation"
      >
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <a
              href="/"
              className="flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg"
              aria-label="TickerStats home"
            >
              <TrendingUp className="w-6 h-6 text-blue-500" />
              <span className="text-xl font-bold text-white">TickerStats</span>
            </a>

            {/* Desktop nav links */}
            <div className="hidden md:flex items-center gap-8">
              {NAV_SECTIONS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => scrollToSection(s.id)}
                  className={`text-sm transition-colors relative focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded ${
                    activeSection === s.id
                      ? "text-white font-medium"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {s.label}
                  {activeSection === s.id && (
                    <span className="absolute -bottom-1 left-0 right-0 h-0.5 bg-blue-500 rounded-full" />
                  )}
                </button>
              ))}
            </div>

            {/* Desktop CTA */}
            <div className="hidden md:block">
              <button
                onClick={handlePrimaryCTA}
                className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg font-medium transition-colors text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
              >
                {primaryCTALabel}
              </button>
            </div>

            {/* Mobile menu toggle */}
            <button
              onClick={() => setMobileMenuOpen((v) => !v)}
              className="md:hidden p-2 text-slate-300 hover:text-white transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg"
              aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? (
                <X className="w-5 h-5" />
              ) : (
                <Menu className="w-5 h-5" />
              )}
            </button>
          </div>

          {/* Mobile menu */}
          {mobileMenuOpen && (
            <div className="md:hidden mt-4 p-3 border border-slate-700/80 rounded-2xl bg-slate-950/95 backdrop-blur-md shadow-2xl shadow-black/40 space-y-2">
              {NAV_SECTIONS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => scrollToSection(s.id)}
                  className={`block w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    activeSection === s.id
                      ? "text-white bg-slate-800/50 font-medium"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/30"
                  }`}
                >
                  {s.label}
                </button>
              ))}
              <button
                onClick={handlePrimaryCTA}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-lg font-medium transition-colors text-sm mt-2"
              >
                {primaryCTALabel}
              </button>
            </div>
          )}
        </div>
      </nav>

      {/* ── Main content ─────────────────────────────────────────────── */}
      <main id="main-content">
        {/* ── HERO ─────────────────────────────────────────────────── */}
        <InteractiveHero>
          <section
            className="min-h-[100svh] flex flex-col items-center justify-center px-4 sm:px-6 pt-24 sm:pt-20 pb-8 sm:pb-0 relative print:min-h-0 print:pt-8 print:pb-8 print:break-inside-avoid"
            aria-label="Hero"
          >
            <motion.div
              className="max-w-5xl mx-auto text-center w-full"
              initial={prefersReduced ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: prefersReduced ? 0.2 : 0.3, ease: "easeOut" }}
            >
              {/* Badge pill */}
              <motion.div
                className="relative z-10 inline-flex items-center gap-2 px-3 sm:px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs sm:text-sm text-slate-300 font-medium mb-5 sm:mb-6"
                initial={prefersReduced ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  duration: prefersReduced ? 0.2 : 0.32,
                  delay: badgeDelay,
                  ease: "easeOut",
                }}
              >
                Compare + DCF + AI Pitch Decks
              </motion.div>

              {/* Headline */}
              <div className="overflow-hidden mb-5">
                <motion.h1
                  className="relative z-10 text-4xl sm:text-6xl lg:text-7xl font-bold text-white leading-[1.08] tracking-tight [text-shadow:0_8px_26px_rgba(2,6,23,0.48)]"
                  initial={prefersReduced ? false : { y: 56 }}
                  animate={{ y: 0 }}
                  transition={{
                    duration: prefersReduced ? 0.22 : 0.4,
                    delay: headlineDelay,
                    ease: "easeOut",
                  }}
                >
                  Your next pitch deck starts with a{" "}
                  <motion.span
                    className="bg-gradient-to-r from-blue-400 via-cyan-300 to-blue-500 bg-clip-text text-transparent"
                    animate={
                      prefersReduced
                        ? undefined
                        : {
                            filter: [
                              "drop-shadow(0 0 0 rgba(56,189,248,0))",
                              "drop-shadow(0 0 10px rgba(56,189,248,0.35))",
                              "drop-shadow(0 0 0 rgba(56,189,248,0))",
                            ],
                          }
                    }
                    transition={
                      prefersReduced
                        ? undefined
                        : {
                            duration: 12,
                            repeat: Infinity,
                            ease: "linear",
                          }
                    }
                  >
                    ticker.
                  </motion.span>
                </motion.h1>
              </div>

              {/* Subhead */}
              <motion.p
                className="relative z-10 text-base sm:text-xl md:text-2xl text-slate-300 mb-6 font-light max-w-3xl mx-auto"
                initial={prefersReduced ? false : { opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  duration: prefersReduced ? 0.2 : 0.3,
                  delay: subtextDelay,
                  ease: "easeOut",
                }}
              >
                TickerStats builds comp tables, runs DCF, and writes
                presentation-ready decks, all from a list of tickers.
              </motion.p>

              {/* CTAs - "Try the demo" is primary */}
              <div className="relative z-10 mt-2 flex flex-wrap gap-3 sm:gap-4 justify-center mb-5 sm:mb-6">
                <motion.button
                  onClick={() => scrollToSection("demos")}
                  className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-6 sm:px-8 py-3 sm:py-4 rounded-lg font-semibold text-sm sm:text-base transition-all inline-flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20 hover:shadow-blue-600/30 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
                  initial={prefersReduced ? false : { opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    duration: prefersReduced ? 0.2 : 0.3,
                    delay: primaryButtonDelay,
                    ease: "easeOut",
                  }}
                >
                  Try the demo
                  <ArrowRight className="w-5 h-5" />
                </motion.button>
                <motion.button
                  onClick={handlePrimaryCTA}
                  className="w-full sm:w-auto bg-white/5 hover:bg-white/10 text-white px-6 sm:px-8 py-3 sm:py-4 rounded-lg font-semibold text-sm sm:text-base transition-colors border border-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
                  initial={prefersReduced ? false : { opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    duration: prefersReduced ? 0.2 : 0.3,
                    delay: secondaryButtonDelay,
                    ease: "easeOut",
                  }}
                >
                  {primaryCTALabel}
                </motion.button>
              </div>

              {/* Trust indicators */}
              <motion.div
                className="relative z-10 flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-xs sm:text-sm text-slate-500"
                initial={prefersReduced ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  duration: prefersReduced ? 0.2 : 0.28,
                  delay: trustDelay,
                  ease: "easeOut",
                }}
              >
                <span className="inline-flex items-center gap-1.5">
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                  100 tickers
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <CheckCircle className="w-4 h-4 text-cyan-400" />
                  Sourced metrics
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <CheckCircle className="w-4 h-4 text-blue-400" />
                  No hallucinations
                </span>
              </motion.div>
            </motion.div>

            {/* Scroll-down indicator */}
            <motion.div
              className="hidden sm:block absolute bottom-6 sm:bottom-8 left-1/2 -translate-x-1/2 print:hidden pointer-events-none"
              animate={
                prefersReduced
                  ? undefined
                  : { y: [0, 5, 0], opacity: [0.35, 0.62, 0.35] }
              }
              transition={
                prefersReduced
                  ? undefined
                  : {
                      duration: 12,
                      repeat: Infinity,
                      ease: "linear",
                    }
              }
            >
              <ChevronDown className="w-6 h-6 text-slate-500" />
            </motion.div>
          </section>
        </InteractiveHero>

        {/* ── HOW IT WORKS ───────────────────────────────────────── */}
        <section
          id="how-it-works"
          className="scroll-mt-24 py-12 md:py-16 px-4 sm:px-6 bg-slate-900/30 print:break-inside-avoid"
          aria-label="How it works"
        >
          <div className="max-w-5xl mx-auto">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-3 text-center">
              How it works
            </h2>
            <p className="text-lg text-slate-400 mb-12 text-center max-w-2xl mx-auto">
              Three steps from ticker to presentation.
            </p>

            <div className="grid md:grid-cols-3 gap-8">
              {/* Step 1 */}
              <div className="text-center">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-blue-500/10 border border-blue-500/20 mb-4">
                  <Search className="w-5 h-5 text-blue-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  1. Pick your tickers
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Enter up to 100 symbols or let us suggest peers by sector.
                </p>
              </div>

              {/* Step 2 */}
              <div className="text-center">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-cyan-500/10 border border-cyan-500/20 mb-4">
                  <Zap className="w-5 h-5 text-cyan-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  2. Generate
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Comp table + AI pitch deck built in parallel. 30–60 seconds.
                </p>
              </div>

              {/* Step 3 */}
              <div className="text-center">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 mb-4">
                  <Repeat className="w-5 h-5 text-emerald-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  3. Present & iterate
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Regenerate any section, export to PDF/PPTX, defend your
                  thesis.
                </p>
              </div>
            </div>

            <div className="relative mt-12 sm:mt-14 h-[96px] sm:h-[124px] lg:h-[136px]">
              <div className="absolute left-1/2 top-1/2 z-0 h-[96px] w-full max-w-[94vw] -translate-x-1/2 -translate-y-1/2 pointer-events-none opacity-[0.9] sm:h-[124px] sm:max-w-[820px] lg:h-[136px] lg:max-w-[900px]">
                <HeroPipeline />
              </div>
            </div>
          </div>
        </section>

        {/* ── INTERACTIVE DEMOS ────────────────────────────────────── */}
        <section
          id="demos"
          ref={demos.ref}
          className={`scroll-mt-24 py-12 md:py-16 px-4 sm:px-6 transition-all duration-700 print:break-inside-avoid ${
            demos.visible
              ? "opacity-100 translate-y-0"
              : "opacity-0 translate-y-8"
          }`}
          aria-label="Interactive product demos"
        >
          <div className="max-w-7xl mx-auto">
            {/* Pre-header: persona strip + trust callout */}
            <div className="space-y-6 md:space-y-8 mb-16 md:mb-20">
              {/* Who it's for */}
              <div className="text-center" aria-label="Who it's for">
                <h3 className="text-xl md:text-2xl font-semibold text-white mb-6">
                  Built for student funds, class pitches, and research teams
                </h3>
                <div className="flex flex-wrap items-center justify-center gap-8 text-sm text-slate-400">
                  <span className="inline-flex items-center gap-2">
                    <Users className="w-4 h-4 text-blue-400" />
                    Investment club comps
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <Trophy className="w-4 h-4 text-amber-400" />
                    Pitch competitions
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <GraduationCap className="w-4 h-4 text-emerald-400" />
                    Finance courses
                  </span>
                </div>
              </div>

              {/* Condensed trust callout */}
              <div className="flex flex-wrap items-center justify-center gap-6 text-sm">
                <span className="inline-flex items-center gap-2 text-slate-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  Numbers are computed
                </span>
                <span className="inline-flex items-center gap-2 text-slate-400">
                  <span className="w-2 h-2 rounded-full bg-blue-400" />
                  Narrative is written
                </span>
                <span className="inline-flex items-center gap-2 text-slate-400">
                  <span className="w-2 h-2 rounded-full bg-amber-400" />
                  Claims are flagged
                </span>
              </div>
            </div>

            <h2 className="text-3xl md:text-4xl font-bold text-white mb-3 text-center">
              See it in action
            </h2>
            <p className="text-lg text-slate-400 mb-12 text-center max-w-2xl mx-auto">
              Try the real product experience right here, no sign-up needed.
            </p>

            {/* Demo A: Comp table */}
            <div className="mb-16">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-xs font-bold text-blue-400 uppercase tracking-wider">
                  Demo
                </span>
                <h3 className="text-xl font-bold text-white">
                  Interactive Comp Table
                </h3>
              </div>
              <p className="text-sm text-slate-400 mb-2 max-w-xl">
                Pick tickers, choose a time window, and toggle metric groups.
                This is what the real product looks like.
              </p>
              <p className="text-xs italic text-slate-500 mb-5">
                Start by selecting 3–5 tickers, then switch Valuation →
                Performance + Risk.
              </p>
              <InteractiveCompDemo />
            </div>

            {/* Demo B: Deck preview */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <span className="text-xs font-bold text-blue-400 uppercase tracking-wider">
                  Demo
                </span>
                <h3 className="text-xl font-bold text-white">
                  AI Pitch Deck Preview
                </h3>
              </div>
              <p className="text-sm text-slate-400 mb-5 max-w-xl">
                Click a section, read the AI-generated content, and hit
                Regenerate to see a new variation. Every claim is flagged for
                verification.
              </p>
              <InteractiveDeckDemo />
            </div>
          </div>
        </section>

        {/* ── TRUST ────────────────────────────────────────────────── */}
        <section
          id="trust"
          ref={trust.ref}
          className={`scroll-mt-24 py-16 md:py-20 px-4 sm:px-6 bg-slate-900/30 transition-all duration-700 ${
            trust.visible
              ? "opacity-100 translate-y-0"
              : "opacity-0 translate-y-8"
          }`}
          aria-label="Trust and transparency"
        >
          <div className="max-w-7xl mx-auto">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-3 text-center">
              Built for defendable research
            </h2>
            <p className="text-lg text-slate-400 mb-12 text-center max-w-2xl mx-auto">
              Transparency and accuracy matter when you present to peers and
              professors.
            </p>

            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
              <TrustCard
                icon={<Shield className="w-5 h-5 text-blue-400" />}
                title="Computed vs written"
                description="Metrics + DCF are deterministic. AI writes narrative only, no hallucinated numbers."
              />
              <TrustCard
                icon={<Clock className="w-5 h-5 text-emerald-400" />}
                title="Sourced & timestamped"
                description="Every metric links to its data source and pull timestamp. Hover any number to verify."
              />
              <TrustCard
                icon={<Flag className="w-5 h-5 text-amber-400" />}
                title="Claim checks"
                description="AI-generated claims are flagged with verification badges so you know what to double-check."
              />
              <TrustCard
                icon={<Eye className="w-5 h-5 text-purple-400" />}
                title="Transparent DCF"
                description="All DCF assumptions (growth, WACC, terminal rate) are visible and editable."
              />
            </div>

            <p className="text-xs text-slate-500 mt-8 text-center">
              For research and education. Not investment advice.
            </p>
          </div>
        </section>

        {/* ── PRICING ──────────────────────────────────────────────── */}
        <section
          id="pricing"
          ref={pricing.ref}
          className={`scroll-mt-24 py-16 md:py-20 px-4 sm:px-6 transition-all duration-700 ${
            pricing.visible
              ? "opacity-100 translate-y-0"
              : "opacity-0 translate-y-8"
          }`}
          aria-label="Pricing plans"
        >
          <div className="max-w-7xl mx-auto">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-3 text-center">
              Simple, transparent pricing
            </h2>
            <p className="text-lg text-slate-400 mb-12 text-center max-w-2xl mx-auto">
              Generate for free, pay only when you export a finished deck.
            </p>

            {/* Pricing cards: Free + export + contact */}
            <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto mb-12 print:break-inside-avoid">
              {/* Free tier */}
              <PricingCard
                name={TIERS.free.name}
                price={TIERS.free.price}
                period={TIERS.free.period}
                features={TIERS.free.features}
                cta={isAuthenticated ? "Go to app" : "Sign up free"}
                onClick={handlePrimaryCTA}
                highlighted={false}
              />

              {/* One-time export */}
              <PricingCard
                name={TIERS.pro.name}
                price={TIERS.pro.price}
                period={TIERS.pro.period}
                features={TIERS.pro.features}
                cta={isResolvingTier ? "Checking account..." : exportCTALabel}
                onClick={handleExportCTA}
                disabled={isResolvingTier || isCreatingCheckout}
                highlighted
              />

              {/* Contact / Need more */}
              <div className="rounded-xl p-8 bg-slate-900 border border-slate-800 flex flex-col">
                <h3 className="text-xl font-bold text-white mb-2">
                  Need more?
                </h3>
                <p className="text-sm text-slate-400 mb-6 flex-1">
                  Need a larger limit or a custom workflow? Reach out and we'll
                  figure it out together.
                </p>
                <button
                  onClick={() => navigate("/contact")}
                  className="w-full py-3 rounded-lg font-semibold transition-colors bg-slate-800 text-white hover:bg-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                >
                  Contact us
                </button>
              </div>
            </div>

            {/* Model note */}
            <div className="text-center mb-12">
              <p className="text-xs text-slate-500">
                Models: Auto (Best Available) selects from {MODELS.join(", ")}.
                <br />
                Model availability may change. TickerStats automatically selects
                the best available model for your deck.
              </p>
            </div>

            {/* Pricing calculator */}
            <div className="max-w-2xl mx-auto">
              <PricingCalculator />
            </div>
          </div>
        </section>

        {/* ── FINAL CTA ────────────────────────────────────────────── */}
        <section
          ref={cta.ref}
          className={`py-16 md:py-20 px-4 sm:px-6 bg-slate-900/30 transition-all duration-700 ${
            cta.visible
              ? "opacity-100 translate-y-0"
              : "opacity-0 translate-y-8"
          }`}
          aria-label="Call to action"
        >
          <div className="max-w-4xl mx-auto text-center">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Ready for your next pitch?
            </h2>
            <p className="text-lg text-slate-400 mb-8">
              Go from ticker list to presentation-ready deck in under a minute.
            </p>
            <div className="flex flex-wrap gap-3 justify-center">
              <button
                onClick={handlePrimaryCTA}
                className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3.5 rounded-lg font-semibold transition-all inline-flex items-center gap-2 shadow-lg shadow-blue-600/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                {primaryCTALabel}
                <ArrowRight className="w-4 h-4" />
              </button>
              <button
                onClick={() => scrollToSection("demos")}
                className="bg-slate-800 hover:bg-slate-700 text-white px-8 py-3.5 rounded-lg font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                Try the demo
              </button>
            </div>
          </div>
        </section>

        {/* ── FAQ ──────────────────────────────────────────────────── */}
        <section
          id="faq"
          ref={faq.ref}
          className={`scroll-mt-24 py-16 md:py-20 px-4 sm:px-6 transition-all duration-700 ${
            faq.visible
              ? "opacity-100 translate-y-0"
              : "opacity-0 translate-y-8"
          }`}
          aria-label="Frequently asked questions"
        >
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-12 text-center">
              Frequently asked questions
            </h2>
            <div className="space-y-4">
              <FAQItem
                question="Where does the data come from?"
                answer="All market data, financials, and metrics come from Yahoo Finance via the yfinance library. Data is timestamped and traceable."
              />
              <FAQItem
                question="What parts are deterministic vs AI-generated?"
                answer="All numbers (metrics, DCF calculations, comparables) are computed deterministically using formulas and market data. AI generates only the narrative text: thesis statements, qualitative analysis, and bullet explanations."
              />
              <FAQItem
                question="What AI models are available?"
                answer={`TickerStats uses Auto (Best Available) by default, selecting from ${MODELS.join(", ")}. Model availability may change as we tune quality and cost.`}
              />
              <FAQItem
                question="Can I choose peer companies?"
                answer="Yes. You can select specific tickers for peer comparison or let the system auto-select based on sector. The comp table supports up to 100 tickers."
              />
              <FAQItem
                question="How fast is generation?"
                answer="Most decks generate in 30–60 seconds. Sections are generated in parallel for speed. Cached data makes subsequent runs even faster."
              />
              <FAQItem
                question="Is this investment advice?"
                answer="No. TickerStats is a research and educational tool. All outputs are for informational purposes only. Always do your own due diligence and consult professionals for investment decisions."
              />
            </div>
          </div>
        </section>
      </main>

      {/* ── FOOTER ───────────────────────────────────────────────── */}
      <footer
        className="py-10 px-4 sm:px-6 border-t border-slate-800"
        aria-label="Footer"
      >
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
              <a href="/contact" className="hover:text-white transition-colors">
                Contact
              </a>
            </div>
            <div className="text-sm text-slate-500 text-center">
              <span>&copy; 2026 TickerStats. All rights reserved.</span>
              <br />
              <span className="text-xs text-slate-600">
                For research and education. Not investment advice.
              </span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

// ─── Sub-components ─────────────────────────────────────────────────────────

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
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 hover:border-slate-700 transition-colors">
      <div className="mb-3">{icon}</div>
      <h3 className="text-base font-semibold text-white mb-2">{title}</h3>
      <p className="text-sm text-slate-400 leading-relaxed">{description}</p>
    </div>
  );
}

function PricingCard({
  name,
  price,
  period,
  features,
  cta,
  onClick,
  disabled = false,
  highlighted = false,
}: {
  name: string;
  price: string;
  period: string;
  features: readonly { text: string; included: boolean }[];
  cta: string;
  onClick: () => void;
  disabled?: boolean;
  highlighted?: boolean;
}) {
  return (
    <div
      className={`rounded-xl p-8 flex flex-col transition-shadow print:break-inside-avoid ${
        highlighted
          ? "bg-gradient-to-b from-blue-600 to-blue-700 border-2 border-blue-500 shadow-xl shadow-blue-600/20 md:scale-105"
          : "bg-slate-900 border border-slate-800"
      }`}
    >
      {highlighted && (
        <span className="text-[10px] uppercase tracking-wider font-bold text-blue-200 mb-2">
          Pay Per Deck
        </span>
      )}
      <h3 className="text-xl font-bold text-white mb-2">{name}</h3>
      <div className="mb-6">
        <span className="text-4xl font-bold text-white">{price}</span>
        <span
          className={`text-sm ml-1 ${
            highlighted ? "text-blue-100" : "text-slate-400"
          }`}
        >
          {period}
        </span>
      </div>
      <ul className="space-y-3 mb-8 flex-1">
        {features.map((f) => (
          <li
            key={f.text}
            className={`flex items-start gap-2 text-sm ${
              f.included
                ? highlighted
                  ? "text-blue-50"
                  : "text-slate-300"
                : highlighted
                  ? "text-blue-200/50 line-through"
                  : "text-slate-500 line-through"
            }`}
          >
            {f.included ? (
              <CheckCircle
                className={`w-4 h-4 flex-shrink-0 mt-0.5 ${
                  highlighted ? "text-blue-200" : "text-blue-500"
                }`}
              />
            ) : (
              <Lock
                className={`w-4 h-4 flex-shrink-0 mt-0.5 ${
                  highlighted ? "text-blue-300/40" : "text-slate-600"
                }`}
              />
            )}
            <span>{f.text}</span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        className={`w-full py-3 rounded-lg font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
          disabled ? "opacity-70 cursor-not-allowed" : ""
        } ${
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

function FAQItem({ question, answer }: { question: string; answer: string }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-slate-800/30 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500"
        aria-expanded={isOpen}
      >
        <span className="font-semibold text-white text-sm">{question}</span>
        <ChevronDown
          className={`w-5 h-5 text-slate-400 transition-transform duration-200 flex-shrink-0 ml-4 ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>
      <div
        className={`overflow-hidden transition-all duration-300 ${
          isOpen ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="px-6 pb-4 text-sm text-slate-300 leading-relaxed">
          {answer}
        </div>
      </div>
    </div>
  );
}
