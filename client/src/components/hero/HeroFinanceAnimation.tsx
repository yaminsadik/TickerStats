import { motion } from "framer-motion";

// ─── Dramatic bullish chart — heavy glow, vivid colors ───────────────────────

const PRICE_PATH =
  "M 60 400 C 110 395, 145 388, 195 374 C 245 360, 275 366, 325 344 C 375 322, 405 330, 455 302 C 505 274, 535 282, 585 254 C 635 228, 665 234, 715 208 C 765 184, 795 188, 845 164 C 875 150, 900 138, 940 112";

const AREA_PATH = `${PRICE_PATH} L 940 440 L 60 440 Z`;

const CANDLES = [
  { x: 120, o: 396, c: 382, h: 376, l: 404 },
  { x: 180, o: 384, c: 376, h: 368, l: 392 },
  { x: 240, o: 372, c: 358, h: 350, l: 380 },
  { x: 300, o: 360, c: 368, h: 354, l: 376 },
  { x: 360, o: 364, c: 342, h: 334, l: 372 },
  { x: 420, o: 344, c: 316, h: 308, l: 352 },
  { x: 480, o: 320, c: 298, h: 288, l: 328 },
  { x: 540, o: 302, c: 310, h: 296, l: 318 },
  { x: 600, o: 306, c: 268, h: 258, l: 314 },
  { x: 660, o: 272, c: 248, h: 238, l: 280 },
  { x: 720, o: 252, c: 224, h: 214, l: 260 },
  { x: 780, o: 228, c: 206, h: 196, l: 236 },
  { x: 840, o: 210, c: 178, h: 166, l: 218 },
  { x: 900, o: 182, c: 152, h: 140, l: 190 },
] as const;

const CANDLE_W = 26;

const PRICES = [
  { y: 160, label: "192.40" },
  { y: 220, label: "184.70" },
  { y: 280, label: "176.30" },
  { y: 340, label: "168.50" },
  { y: 400, label: "160.10" },
] as const;

const CYCLE = 11;
const LINE_TIMES = [0, 0.6, 0.88, 1.0];

function candleRevealTime(x: number): number {
  return ((x - 60) / (940 - 60)) * 0.6;
}

interface Props {
  prefersReduced: boolean;
}

export default function HeroFinanceAnimation({ prefersReduced }: Props) {
  return (
    <svg
      viewBox="0 0 1000 480"
      preserveAspectRatio="xMidYMid slice"
      className="h-full w-full"
    >
      <defs>
        {/* Line gradient — brighter, more saturated */}
        <linearGradient id="hf-line" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="rgba(56,189,248,0.6)" />
          <stop offset="35%" stopColor="rgba(34,211,238,1)" />
          <stop offset="70%" stopColor="rgba(52,211,153,1)" />
          <stop offset="100%" stopColor="rgba(74,222,128,0.9)" />
        </linearGradient>

        {/* Area fill — richer, more visible */}
        <linearGradient id="hf-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(34,211,238,0.28)" />
          <stop offset="40%" stopColor="rgba(52,211,153,0.12)" />
          <stop offset="100%" stopColor="rgba(34,211,238,0)" />
        </linearGradient>

        {/* Bullish candle — vivid green */}
        <linearGradient id="hf-bull" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(52,211,153,0.85)" />
          <stop offset="100%" stopColor="rgba(52,211,153,0.35)" />
        </linearGradient>

        {/* Bearish candle — cool slate */}
        <linearGradient id="hf-bear" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(148,163,184,0.5)" />
          <stop offset="100%" stopColor="rgba(148,163,184,0.18)" />
        </linearGradient>

        {/* Wide bloom for the line (outer glow layer) */}
        <filter id="hf-bloom-wide" x="-20%" y="-80%" width="140%" height="260%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="10" />
        </filter>

        {/* Mid glow for the line */}
        <filter id="hf-bloom-mid" x="-15%" y="-60%" width="130%" height="220%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="5" />
        </filter>

        {/* Tight glow (close to the line) */}
        <filter id="hf-bloom-tight" x="-10%" y="-50%" width="120%" height="200%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="2.5" />
        </filter>

        {/* Candle glow halo */}
        <filter id="hf-candle-glow" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="6" />
        </filter>

        {/* Area inner glow */}
        <linearGradient id="hf-area-glow" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(56,189,248,0.2)" />
          <stop offset="100%" stopColor="rgba(56,189,248,0)" />
        </linearGradient>
      </defs>

      {/* ── Grid (slightly brighter for framing) ─────────────────── */}
      {Array.from({ length: 7 }).map((_, i) => (
        <line
          key={`h-${i}`}
          x1="50"
          y1={140 + i * 48}
          x2="960"
          y2={140 + i * 48}
          stroke="rgba(56,189,248,0.05)"
          strokeWidth="0.8"
        />
      ))}
      {Array.from({ length: 10 }).map((_, i) => (
        <line
          key={`v-${i}`}
          x1={60 + i * 100}
          y1="120"
          x2={60 + i * 100}
          y2="440"
          stroke="rgba(56,189,248,0.035)"
          strokeWidth="0.6"
        />
      ))}

      {/* ── Y-axis price labels ──────────────────────────────────── */}
      {PRICES.map((p) => (
        <g key={p.label}>
          <text
            x={48}
            y={p.y + 3}
            textAnchor="end"
            fill="rgba(148,163,184,0.22)"
            fontSize="9"
            fontFamily="ui-monospace, SFMono-Regular, monospace"
          >
            {p.label}
          </text>
          <line
            x1="52"
            y1={p.y}
            x2="58"
            y2={p.y}
            stroke="rgba(148,163,184,0.15)"
            strokeWidth="0.8"
          />
        </g>
      ))}

      {/* ── X-axis ───────────────────────────────────────────────── */}
      <line
        x1="56"
        y1="440"
        x2="960"
        y2="440"
        stroke="rgba(148,163,184,0.09)"
        strokeWidth="0.8"
      />

      {/* ── Area fill ────────────────────────────────────────────── */}
      <motion.path
        d={AREA_PATH}
        fill="url(#hf-area)"
        initial={prefersReduced ? false : { opacity: 0 }}
        animate={
          prefersReduced
            ? { opacity: 0.3 }
            : { opacity: [0, 0.55, 0.55, 0] }
        }
        transition={
          prefersReduced
            ? undefined
            : {
                duration: CYCLE,
                repeat: Infinity,
                times: LINE_TIMES,
                ease: "easeOut",
              }
        }
      />

      {/* ── Candlesticks ─────────────────────────────────────────── */}
      {CANDLES.map((c, i) => {
        const bull = c.c < c.o;
        const bodyTop = Math.min(c.o, c.c);
        const bodyH = Math.max(Math.abs(c.c - c.o), 3);
        const bodyMid = bodyTop + bodyH / 2;
        const reveal = candleRevealTime(c.x);
        const cTimes = [0, Math.max(0, reveal - 0.025), reveal, 0.88, 1.0];

        return (
          <g key={`c-${i}`}>
            {/* Candle glow halo (bullish only) */}
            {bull && !prefersReduced && (
              <motion.ellipse
                cx={c.x}
                cy={bodyMid}
                rx={20}
                ry={bodyH * 0.8 + 10}
                fill="rgba(52,211,153,0.25)"
                filter="url(#hf-candle-glow)"
                initial={{ opacity: 0 }}
                animate={{ opacity: [0, 0, 0.6, 0.4, 0] }}
                transition={{
                  duration: CYCLE,
                  repeat: Infinity,
                  times: cTimes,
                  ease: "linear",
                }}
              />
            )}
            {/* Wick */}
            <motion.line
              x1={c.x}
              y1={c.h}
              x2={c.x}
              y2={c.l}
              stroke={
                bull
                  ? "rgba(52,211,153,0.5)"
                  : "rgba(148,163,184,0.25)"
              }
              strokeWidth="1.5"
              initial={prefersReduced ? false : { opacity: 0 }}
              animate={
                prefersReduced
                  ? { opacity: 0.5 }
                  : { opacity: [0, 0, 0.7, 0.7, 0] }
              }
              transition={
                prefersReduced
                  ? undefined
                  : {
                      duration: CYCLE,
                      repeat: Infinity,
                      times: cTimes,
                      ease: "linear",
                    }
              }
            />
            {/* Body */}
            <motion.rect
              x={c.x - CANDLE_W / 2}
              y={bodyTop}
              width={CANDLE_W}
              height={bodyH}
              rx={2}
              fill={bull ? "url(#hf-bull)" : "url(#hf-bear)"}
              initial={prefersReduced ? false : { opacity: 0 }}
              animate={
                prefersReduced
                  ? { opacity: 0.6 }
                  : { opacity: [0, 0, 0.9, 0.9, 0] }
              }
              transition={
                prefersReduced
                  ? undefined
                  : {
                      duration: CYCLE,
                      repeat: Infinity,
                      times: cTimes,
                      ease: "linear",
                    }
              }
            />
          </g>
        );
      })}

      {/* ── Line glow: layer 1 — wide bloom (outermost) ──────────── */}
      {!prefersReduced && (
        <motion.path
          d={PRICE_PATH}
          fill="none"
          stroke="rgba(56,189,248,0.2)"
          strokeWidth="18"
          strokeLinecap="round"
          filter="url(#hf-bloom-wide)"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{
            pathLength: [0, 1, 1, 0],
            opacity: [0, 0.6, 0.5, 0],
          }}
          transition={{
            duration: CYCLE,
            repeat: Infinity,
            times: LINE_TIMES,
            ease: "easeOut",
          }}
        />
      )}

      {/* ── Line glow: layer 2 — mid bloom ───────────────────────── */}
      {!prefersReduced && (
        <motion.path
          d={PRICE_PATH}
          fill="none"
          stroke="rgba(34,211,238,0.3)"
          strokeWidth="10"
          strokeLinecap="round"
          filter="url(#hf-bloom-mid)"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{
            pathLength: [0, 1, 1, 0],
            opacity: [0, 0.7, 0.6, 0],
          }}
          transition={{
            duration: CYCLE,
            repeat: Infinity,
            times: LINE_TIMES,
            ease: "easeOut",
          }}
        />
      )}

      {/* ── Line glow: layer 3 — tight bloom (closest to line) ───── */}
      {!prefersReduced && (
        <motion.path
          d={PRICE_PATH}
          fill="none"
          stroke="rgba(52,211,153,0.45)"
          strokeWidth="5"
          strokeLinecap="round"
          filter="url(#hf-bloom-tight)"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{
            pathLength: [0, 1, 1, 0],
            opacity: [0, 0.8, 0.7, 0],
          }}
          transition={{
            duration: CYCLE,
            repeat: Infinity,
            times: LINE_TIMES,
            ease: "easeOut",
          }}
        />
      )}

      {/* ── Price line (crisp, bright) ───────────────────────────── */}
      <motion.path
        d={PRICE_PATH}
        fill="none"
        stroke="url(#hf-line)"
        strokeWidth="2.8"
        strokeLinecap="round"
        initial={prefersReduced ? false : { pathLength: 0, opacity: 0.4 }}
        animate={
          prefersReduced
            ? { pathLength: 1, opacity: 0.7 }
            : {
                pathLength: [0, 1, 1, 0],
                opacity: [0.6, 1, 1, 0],
              }
        }
        transition={
          prefersReduced
            ? { duration: 0.5 }
            : {
                duration: CYCLE,
                repeat: Infinity,
                times: LINE_TIMES,
                ease: "easeOut",
              }
        }
      />
    </svg>
  );
}
