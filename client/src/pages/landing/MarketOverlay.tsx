import { motion } from "framer-motion";

interface MarketOverlayProps {
  prefersReduced: boolean;
}

const candles = [
  { x: 130, open: 256, close: 238, high: 228, low: 268 },
  { x: 180, open: 246, close: 234, high: 220, low: 258 },
  { x: 230, open: 238, close: 222, high: 212, low: 252 },
  { x: 280, open: 226, close: 238, high: 210, low: 246 },
  { x: 330, open: 234, close: 216, high: 204, low: 244 },
  { x: 380, open: 220, close: 208, high: 194, low: 236 },
  { x: 430, open: 212, close: 226, high: 190, low: 234 },
  { x: 480, open: 224, close: 202, high: 184, low: 232 },
  { x: 530, open: 206, close: 194, high: 178, low: 222 },
  { x: 580, open: 198, close: 210, high: 170, low: 218 },
  { x: 630, open: 212, close: 188, high: 166, low: 216 },
  { x: 680, open: 192, close: 176, high: 156, low: 206 },
  { x: 730, open: 178, close: 192, high: 152, low: 198 },
  { x: 780, open: 194, close: 170, high: 146, low: 196 },
  { x: 830, open: 174, close: 160, high: 138, low: 186 },
  { x: 880, open: 162, close: 174, high: 130, low: 184 },
  { x: 930, open: 176, close: 158, high: 126, low: 182 },
  { x: 980, open: 162, close: 148, high: 120, low: 174 },
  { x: 1030, open: 152, close: 166, high: 114, low: 170 },
];

const volume = [
  { x: 120, h: 14 },
  { x: 170, h: 18 },
  { x: 220, h: 16 },
  { x: 270, h: 24 },
  { x: 320, h: 20 },
  { x: 370, h: 22 },
  { x: 420, h: 19 },
  { x: 470, h: 26 },
  { x: 520, h: 28 },
  { x: 570, h: 21 },
  { x: 620, h: 30 },
  { x: 670, h: 26 },
  { x: 720, h: 18 },
  { x: 770, h: 32 },
  { x: 820, h: 22 },
  { x: 870, h: 20 },
  { x: 920, h: 27 },
  { x: 970, h: 17 },
  { x: 1020, h: 24 },
];

const tickerTape = [
  { sym: "SPY", chg: "+0.92%" },
  { sym: "QQQ", chg: "+1.14%" },
  { sym: "NVDA", chg: "+2.47%" },
  { sym: "MSFT", chg: "+0.66%" },
  { sym: "AAPL", chg: "-0.42%" },
  { sym: "AMZN", chg: "+0.81%" },
  { sym: "META", chg: "+1.29%" },
];

function TapeRow({ xOffset = 0 }: { xOffset?: number }) {
  return (
    <g transform={`translate(${xOffset} 0)`}>
      {tickerTape.map((item, i) => {
        const x = 56 + i * 170;
        const up = item.chg.startsWith("+");
        return (
          <g key={`${item.sym}-${i}`} transform={`translate(${x} 58)`}>
            <rect
              x="-44"
              y="-14"
              width="136"
              height="28"
              rx="12"
              fill="rgba(2,6,23,0.52)"
              stroke={up ? "rgba(16,185,129,0.40)" : "rgba(244,63,94,0.40)"}
              strokeWidth="1"
            />
            <text
              x="-26"
              y="4"
              fill="#cbd5e1"
              fontSize="11"
              fontWeight="600"
              letterSpacing="0.3"
            >
              {item.sym}
            </text>
            <text
              x="22"
              y="4"
              fill={up ? "#6ee7b7" : "#fda4af"}
              fontSize="11"
              fontWeight="700"
            >
              {item.chg}
            </text>
          </g>
        );
      })}
    </g>
  );
}

export default function MarketOverlay({ prefersReduced }: MarketOverlayProps) {
  return (
    <div
      className="absolute inset-x-0 bottom-[-4%] z-[1] pointer-events-none"
      aria-hidden="true"
      style={{
        maskImage:
          "linear-gradient(to top, rgba(0,0,0,0.98) 0%, rgba(0,0,0,0.92) 62%, rgba(0,0,0,0.45) 86%, rgba(0,0,0,0) 100%)",
      }}
    >
      <svg
        viewBox="0 0 1200 420"
        preserveAspectRatio="xMidYMax slice"
        className="w-full h-[40vh] min-h-[220px] max-h-[360px] opacity-[0.62]"
      >
        <defs>
          <linearGradient id="mo-price" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#38bdf8" />
            <stop offset="45%" stopColor="#22d3ee" />
            <stop offset="100%" stopColor="#34d399" />
          </linearGradient>
          <linearGradient id="mo-area" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(56,189,248,0.18)" />
            <stop offset="100%" stopColor="rgba(52,211,153,0.02)" />
          </linearGradient>
          <filter id="mo-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2.2" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <motion.g
          initial={prefersReduced ? false : { opacity: 0.55 }}
          animate={prefersReduced ? { opacity: 0.55 } : { opacity: [0.48, 0.72, 0.48] }}
          transition={
            prefersReduced
              ? undefined
              : { duration: 6.2, repeat: Infinity, ease: "easeInOut" }
          }
        >
          {Array.from({ length: 9 }).map((_, i) => (
            <line
              key={`h-${i}`}
              x1="0"
              y1={110 + i * 28}
              x2="1200"
              y2={110 + i * 28}
              stroke="rgba(56,189,248,0.08)"
              strokeWidth="1"
            />
          ))}
          {Array.from({ length: 16 }).map((_, i) => (
            <line
              key={`v-${i}`}
              x1={60 + i * 72}
              y1="90"
              x2={60 + i * 72}
              y2="380"
              stroke="rgba(56,189,248,0.06)"
              strokeWidth="1"
            />
          ))}
        </motion.g>

        <motion.g
          initial={prefersReduced ? false : { x: 0 }}
          animate={prefersReduced ? { x: 0 } : { x: [0, -170] }}
          transition={
            prefersReduced
              ? undefined
              : { duration: 16, repeat: Infinity, ease: "linear" }
          }
        >
          <TapeRow />
          <TapeRow xOffset={1190} />
        </motion.g>

        <motion.path
          d="M70 280 C170 244, 250 268, 338 230 C410 198, 488 234, 560 190 C632 152, 710 188, 792 150 C860 120, 932 148, 1008 122 C1060 106, 1100 120, 1136 112 L1136 392 L70 392 Z"
          fill="url(#mo-area)"
          initial={prefersReduced ? false : { opacity: 0.3 }}
          animate={
            prefersReduced
              ? { opacity: 0.3 }
              : { opacity: [0.24, 0.42, 0.24] }
          }
          transition={
            prefersReduced
              ? undefined
              : { duration: 5.8, repeat: Infinity, ease: "easeInOut" }
          }
        />

        <motion.path
          d="M70 280 C170 244, 250 268, 338 230 C410 198, 488 234, 560 190 C632 152, 710 188, 792 150 C860 120, 932 148, 1008 122 C1060 106, 1100 120, 1136 112"
          fill="none"
          stroke="url(#mo-price)"
          strokeWidth="2.2"
          strokeLinecap="round"
          filter="url(#mo-glow)"
          initial={prefersReduced ? false : { pathLength: 0.3, opacity: 0.24 }}
          animate={
            prefersReduced
              ? { pathLength: 1, opacity: 0.6 }
              : { pathLength: [0.3, 1, 0.3], opacity: [0.24, 0.84, 0.24] }
          }
          transition={
            prefersReduced
              ? { duration: 0.35 }
              : { duration: 5.6, repeat: Infinity, ease: "easeInOut" }
          }
        />

        <g>
          {candles.map((c, i) => {
            const up = c.close < c.open;
            const y = Math.min(c.open, c.close);
            const h = Math.max(3, Math.abs(c.open - c.close));
            return (
              <motion.g
                key={c.x}
                initial={prefersReduced ? false : { opacity: 0.18 }}
                animate={
                  prefersReduced
                    ? { opacity: 0.46 }
                    : { opacity: [0.22, 0.68, 0.22] }
                }
                transition={{
                  duration: prefersReduced ? 0 : 2.8,
                  delay: prefersReduced ? 0 : i * 0.07,
                  repeat: prefersReduced ? 0 : Infinity,
                  ease: "easeInOut",
                }}
              >
                <line
                  x1={c.x}
                  y1={c.high}
                  x2={c.x}
                  y2={c.low}
                  stroke={up ? "rgba(52,211,153,0.72)" : "rgba(248,113,113,0.72)"}
                  strokeWidth="1.2"
                />
                <rect
                  x={c.x - 5}
                  y={y}
                  width="10"
                  height={h}
                  rx="1.5"
                  fill={
                    up ? "rgba(52,211,153,0.44)" : "rgba(248,113,113,0.42)"
                  }
                  stroke={
                    up ? "rgba(110,231,183,0.86)" : "rgba(254,202,202,0.86)"
                  }
                  strokeWidth="0.8"
                />
              </motion.g>
            );
          })}
        </g>

        <g>
          {volume.map((v, i) => (
            <motion.rect
              key={v.x}
              x={v.x}
              y={384 - v.h}
              width="11"
              height={v.h}
              rx="2"
              fill="rgba(56,189,248,0.24)"
              initial={prefersReduced ? false : { opacity: 0.18 }}
              animate={
                prefersReduced ? { opacity: 0.3 } : { opacity: [0.14, 0.42, 0.14] }
              }
              transition={{
                duration: prefersReduced ? 0 : 2.2,
                delay: prefersReduced ? 0 : i * 0.05,
                repeat: prefersReduced ? 0 : Infinity,
                ease: "easeInOut",
              }}
            />
          ))}
        </g>
      </svg>
    </div>
  );
}
