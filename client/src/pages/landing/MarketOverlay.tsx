import { motion } from "framer-motion";

interface MarketOverlayProps {
  prefersReduced: boolean;
}

const tickerFeed = [
  { sym: "SPY", price: "521.40", chg: "+0.92%" },
  { sym: "QQQ", price: "446.88", chg: "+1.14%" },
  { sym: "NVDA", price: "954.31", chg: "+2.47%" },
  { sym: "MSFT", price: "428.74", chg: "+0.66%" },
  { sym: "AAPL", price: "201.12", chg: "-0.42%" },
  { sym: "AMZN", price: "188.40", chg: "+0.81%" },
  { sym: "META", price: "519.77", chg: "+1.29%" },
  { sym: "TSLA", price: "241.60", chg: "-0.95%" },
];

const watchlist = [
  { sym: "NVDA", last: "954.31", chg: "+2.47%", vol: "44.2M" },
  { sym: "MSFT", last: "428.74", chg: "+0.66%", vol: "18.1M" },
  { sym: "AMZN", last: "188.40", chg: "+0.81%", vol: "27.3M" },
  { sym: "AAPL", last: "201.12", chg: "-0.42%", vol: "56.7M" },
  { sym: "TSLA", last: "241.60", chg: "-0.95%", vol: "71.0M" },
  { sym: "META", last: "519.77", chg: "+1.29%", vol: "14.8M" },
];

const orderBook = [
  { side: "ASK", price: "521.42", size: 140, width: 88 },
  { side: "ASK", price: "521.41", size: 112, width: 70 },
  { side: "ASK", price: "521.40", size: 96, width: 58 },
  { side: "BID", price: "521.39", size: 118, width: 74 },
  { side: "BID", price: "521.38", size: 150, width: 94 },
  { side: "BID", price: "521.37", size: 132, width: 82 },
];

function MarketTickerRow() {
  return (
    <>
      {tickerFeed.map((item, i) => {
        const up = item.chg.startsWith("+");
        return (
          <div
            key={`${item.sym}-${i}`}
            className="inline-flex items-center gap-2 border-r border-slate-700/70 px-4 py-1.5"
          >
            <span className="text-slate-300 font-semibold">{item.sym}</span>
            <span className="text-slate-400 tabular-nums">{item.price}</span>
            <span
              className={`tabular-nums font-semibold ${
                up ? "text-emerald-300" : "text-rose-300"
              }`}
            >
              {item.chg}
            </span>
          </div>
        );
      })}
    </>
  );
}

export default function MarketOverlay({ prefersReduced }: MarketOverlayProps) {
  return (
    <div
      className="absolute inset-x-0 bottom-[-3%] z-[1] pointer-events-none px-4 sm:px-8"
      aria-hidden="true"
      style={{
        maskImage:
          "linear-gradient(to top, rgba(0,0,0,0.98) 0%, rgba(0,0,0,0.9) 66%, rgba(0,0,0,0.36) 88%, rgba(0,0,0,0) 100%)",
      }}
    >
      <motion.div
        className="relative mx-auto max-w-6xl rounded-2xl border border-cyan-400/25 bg-slate-950/60 shadow-[0_0_80px_rgba(34,211,238,0.08)] backdrop-blur-xl overflow-hidden"
        initial={prefersReduced ? false : { opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={
          prefersReduced
            ? { duration: 0.35, ease: "easeOut" }
            : { duration: 0.4, ease: "easeOut" }
        }
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_10%_20%,rgba(56,189,248,0.16),transparent_45%),radial-gradient(circle_at_90%_15%,rgba(52,211,153,0.10),transparent_40%),linear-gradient(to_bottom,rgba(2,6,23,0.98),rgba(2,6,23,0.78))]" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(56,189,248,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(56,189,248,0.05)_1px,transparent_1px)] bg-[size:2.3rem_2.3rem] opacity-35" />
        {!prefersReduced && (
          <motion.div
            className="absolute inset-y-0 w-[20%] bg-[linear-gradient(to_right,transparent,rgba(34,211,238,0.11),transparent)]"
            animate={{ x: ["-30%", "620%"] }}
            transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
          />
        )}

        <div className="relative">
          <div className="flex items-center justify-between border-b border-cyan-400/20 px-4 py-2.5 text-[10px] sm:text-[11px] tracking-[0.14em] uppercase">
            <div className="inline-flex items-center gap-2 text-cyan-300/95">
              <motion.span
                className="h-1.5 w-1.5 rounded-full bg-emerald-300"
                animate={prefersReduced ? undefined : { opacity: [0.4, 1, 0.4] }}
                transition={
                  prefersReduced
                    ? undefined
                    : { duration: 12, repeat: Infinity, ease: "linear" }
                }
              />
              LIVE MARKET TERMINAL
            </div>
            <div className="hidden sm:inline-flex items-center gap-3 text-slate-400">
              <span>US EQUITIES</span>
              <span>LATENCY 21MS</span>
              <span>FEED: REALTIME</span>
            </div>
          </div>

          <div className="overflow-hidden border-b border-cyan-400/15 bg-slate-950/40">
            <motion.div
              className="whitespace-nowrap text-[11px] sm:text-xs"
              animate={prefersReduced ? { x: 0 } : { x: ["0%", "-50%"] }}
              transition={
                prefersReduced
                  ? undefined
                  : { duration: 18, repeat: Infinity, ease: "linear" }
              }
            >
              <span className="inline-flex">
                <MarketTickerRow />
                <MarketTickerRow />
              </span>
            </motion.div>
          </div>

          <div className="grid grid-cols-1 gap-3 px-3 pb-3 pt-3 md:grid-cols-12 md:gap-2.5">
            <section className="rounded-xl border border-slate-700/80 bg-slate-950/55 p-2.5 md:col-span-4">
              <div className="mb-2 text-[10px] uppercase tracking-[0.13em] text-cyan-300/80">
                Watchlist
              </div>
              <div className="space-y-1.5 text-[11px]">
                {watchlist.map((row, i) => {
                  const up = row.chg.startsWith("+");
                  return (
                    <motion.div
                      key={row.sym}
                      className="grid grid-cols-[48px_1fr_64px_54px] items-center rounded-md border border-slate-800/80 bg-slate-900/40 px-2 py-1"
                      animate={
                        prefersReduced
                          ? undefined
                          : { borderColor: ["rgba(30,41,59,0.8)", "rgba(34,211,238,0.32)", "rgba(30,41,59,0.8)"] }
                      }
                      transition={
                        prefersReduced
                          ? undefined
                          : { duration: 12, delay: i * 0.2, repeat: Infinity, ease: "linear" }
                      }
                    >
                      <span className="font-semibold text-slate-200">{row.sym}</span>
                      <span className="tabular-nums text-slate-400">{row.last}</span>
                      <span
                        className={`tabular-nums text-right font-semibold ${
                          up ? "text-emerald-300" : "text-rose-300"
                        }`}
                      >
                        {row.chg}
                      </span>
                      <span className="tabular-nums text-right text-slate-500">
                        {row.vol}
                      </span>
                    </motion.div>
                  );
                })}
              </div>
            </section>

            <section className="rounded-xl border border-slate-700/80 bg-slate-950/55 p-2.5 md:col-span-5">
              <div className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-[0.13em]">
                <span className="text-cyan-300/80">TSLA Intraday</span>
                <span className="tabular-nums text-emerald-300">+1.87%</span>
              </div>
              <div className="rounded-lg border border-slate-800/80 bg-slate-950/65 p-1.5">
                <svg viewBox="0 0 460 170" className="h-[130px] w-full">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <line
                      key={`h-${i}`}
                      x1="0"
                      y1={15 + i * 28}
                      x2="460"
                      y2={15 + i * 28}
                      stroke="rgba(56,189,248,0.09)"
                      strokeWidth="1"
                    />
                  ))}
                  {Array.from({ length: 8 }).map((_, i) => (
                    <line
                      key={`v-${i}`}
                      x1={i * 65}
                      y1="0"
                      x2={i * 65}
                      y2="170"
                      stroke="rgba(56,189,248,0.06)"
                      strokeWidth="1"
                    />
                  ))}
                  <motion.path
                    d="M6 140 C44 120, 78 132, 112 104 C146 84, 184 112, 218 92 C252 72, 294 100, 328 70 C358 48, 392 64, 454 38"
                    fill="none"
                    stroke="rgba(34,211,238,0.95)"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    initial={prefersReduced ? false : { pathLength: 0.2, opacity: 0.2 }}
                    animate={
                      prefersReduced
                        ? { pathLength: 1, opacity: 0.7 }
                        : {
                            pathLength: [0.92, 1, 0.92],
                            opacity: [0.5, 0.88, 0.5],
                          }
                    }
                    transition={
                      prefersReduced
                        ? { duration: 0.35, ease: "easeOut" }
                        : { duration: 12, repeat: Infinity, ease: "linear" }
                    }
                  />
                  <motion.path
                    d="M6 140 C44 120, 78 132, 112 104 C146 84, 184 112, 218 92 C252 72, 294 100, 328 70 C358 48, 392 64, 454 38 L454 170 L6 170 Z"
                    fill="rgba(34,211,238,0.12)"
                    initial={prefersReduced ? false : { opacity: 0.2 }}
                    animate={
                      prefersReduced ? { opacity: 0.22 } : { opacity: [0.14, 0.28, 0.14] }
                    }
                    transition={
                      prefersReduced
                        ? undefined
                        : { duration: 12, repeat: Infinity, ease: "linear" }
                    }
                  />
                </svg>
              </div>
              <div className="mt-2 grid grid-cols-3 gap-1.5 text-[10px] sm:text-[11px]">
                <div className="rounded-md border border-slate-800/70 bg-slate-900/45 px-2 py-1 text-slate-400">
                  VWAP <span className="tabular-nums text-slate-200">239.44</span>
                </div>
                <div className="rounded-md border border-slate-800/70 bg-slate-900/45 px-2 py-1 text-slate-400">
                  RSI <span className="tabular-nums text-emerald-300">61.2</span>
                </div>
                <div className="rounded-md border border-slate-800/70 bg-slate-900/45 px-2 py-1 text-slate-400">
                  Vol <span className="tabular-nums text-cyan-300">2.3M</span>
                </div>
              </div>
            </section>

            <section className="rounded-xl border border-slate-700/80 bg-slate-950/55 p-2.5 md:col-span-3">
              <div className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-[0.13em]">
                <span className="text-cyan-300/80">Order Book</span>
                <span className="tabular-nums text-slate-400">SPY</span>
              </div>
              <div className="space-y-1.5 text-[11px]">
                {orderBook.map((level, i) => {
                  const ask = level.side === "ASK";
                  return (
                    <div
                      key={`${level.side}-${level.price}`}
                      className="relative overflow-hidden rounded-md border border-slate-800/80 bg-slate-900/50 px-2 py-1.5"
                    >
                      <motion.div
                        className={`absolute inset-y-0 ${
                          ask ? "right-0 bg-rose-400/14" : "left-0 bg-emerald-400/14"
                        }`}
                        style={{ width: `${level.width}%` }}
                        animate={
                          prefersReduced
                            ? undefined
                            : { opacity: [0.25, 0.55, 0.25] }
                        }
                        transition={{
                          duration: prefersReduced ? 0 : 11,
                          delay: prefersReduced ? 0 : i * 0.1,
                          repeat: prefersReduced ? 0 : Infinity,
                          ease: "linear",
                        }}
                      />
                      <div className="relative grid grid-cols-[34px_1fr_48px] items-center">
                        <span
                          className={`font-semibold ${
                            ask ? "text-rose-300" : "text-emerald-300"
                          }`}
                        >
                          {level.side}
                        </span>
                        <span className="tabular-nums text-center text-slate-300">
                          {level.price}
                        </span>
                        <span className="tabular-nums text-right text-slate-500">
                          {level.size}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="mt-2 rounded-md border border-cyan-400/25 bg-cyan-400/5 px-2 py-1 text-[10px] text-cyan-300/90">
                Spread 0.03 | Imbalance +0.18
              </div>
            </section>
          </div>

          <div className="grid grid-cols-3 border-t border-slate-700/70 text-[10px] sm:text-[11px]">
            <div className="border-r border-slate-700/70 px-3 py-1.5 text-slate-400">
              Signal Engine: <span className="text-emerald-300">Momentum Long</span>
            </div>
            <div className="border-r border-slate-700/70 px-3 py-1.5 text-slate-400">
              Risk Pulse: <span className="text-cyan-300">Stable</span>
            </div>
            <div className="px-3 py-1.5 text-slate-400">
              Session: <span className="text-slate-200">NYSE Open</span>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
