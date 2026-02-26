import { motion, useReducedMotion } from "framer-motion";

type PipelineNode = {
  id: "ticker" | "relative" | "deck";
  label: string;
  x: number;
  y: number;
};

const NODES: PipelineNode[] = [
  { id: "ticker", label: "Ticker", x: 210, y: 210 },
  { id: "relative", label: "Comps Table", x: 600, y: 188 },
  { id: "deck", label: "Deck", x: 990, y: 210 },
];

const CYCLE_SECONDS = 6;
const IDLE_BREATHE_SECONDS = 12;
const HIT_TIMES = {
  ticker: 0.18,
  relative: 1.1,
  deck: 2.2,
} as const;

function pulseTimes(hitSeconds: number): number[] {
  const hit = hitSeconds / CYCLE_SECONDS;
  return [0, Math.max(0, hit - 0.02), hit, Math.min(1, hit + 0.08)];
}

export default function HeroPipeline() {
  const prefersReduced = useReducedMotion() ?? false;
  const [tickerNode, relativeNode, deckNode] = NODES;

  return (
    // Fills its local slot. Keep at z-0 so nearby copy/CTAs can sit on z-10.
    <div
      className="pointer-events-none absolute inset-0 z-0"
      aria-hidden="true"
    >
      <div className="mx-auto h-full w-full">
        <svg viewBox="0 0 1200 360" className="h-full w-full">
          <defs>
            <linearGradient
              id="pipeline-line"
              x1="0%"
              y1="0%"
              x2="100%"
              y2="0%"
            >
              <stop offset="0%" stopColor="rgba(125,211,252,0.14)" />
              <stop offset="50%" stopColor="rgba(34,211,238,0.30)" />
              <stop offset="100%" stopColor="rgba(56,189,248,0.16)" />
            </linearGradient>
            <radialGradient id="pipeline-node" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(167,243,208,0.34)" />
              <stop offset="100%" stopColor="rgba(56,189,248,0.22)" />
            </radialGradient>
          </defs>

          <motion.line
            x1={tickerNode.x}
            y1={tickerNode.y}
            x2={relativeNode.x}
            y2={relativeNode.y}
            stroke="url(#pipeline-line)"
            strokeWidth="2.8"
            strokeLinecap="round"
            initial={false}
            animate={
              prefersReduced ? undefined : { opacity: [0.62, 0.92, 0.62] }
            }
            transition={
              prefersReduced
                ? undefined
                : {
                    duration: IDLE_BREATHE_SECONDS,
                    ease: "linear",
                    repeat: Infinity,
                  }
            }
          />
          <motion.line
            x1={relativeNode.x}
            y1={relativeNode.y}
            x2={deckNode.x}
            y2={deckNode.y}
            stroke="url(#pipeline-line)"
            strokeWidth="2.8"
            strokeLinecap="round"
            initial={false}
            animate={
              prefersReduced ? undefined : { opacity: [0.58, 0.88, 0.58] }
            }
            transition={
              prefersReduced
                ? undefined
                : {
                    duration: IDLE_BREATHE_SECONDS,
                    ease: "linear",
                    repeat: Infinity,
                    delay: IDLE_BREATHE_SECONDS * 0.2,
                  }
            }
          />

          {NODES.map((node) => {
            const hitSeconds = HIT_TIMES[node.id];
            const times = pulseTimes(hitSeconds);

            return (
              <g key={node.id}>
                <circle
                  cx={node.x}
                  cy={node.y}
                  r="12"
                  fill="url(#pipeline-node)"
                  stroke="rgba(125,211,252,0.50)"
                  strokeWidth="1.6"
                />
                {!prefersReduced && (
                  <motion.circle
                    cx={node.x}
                    cy={node.y}
                    r={12}
                    fill="none"
                    stroke="rgba(45,212,191,0.50)"
                    strokeWidth="1.8"
                    initial={{ opacity: 0, r: 12 }}
                    animate={{
                      opacity: [0, 0, 0.75, 0],
                      r: [12, 12, 22.8, 12],
                    }}
                    transition={{
                      duration: CYCLE_SECONDS,
                      ease: "linear",
                      repeat: Infinity,
                      times,
                    }}
                  />
                )}
                <text
                  x={node.x}
                  y={node.y - 34}
                  textAnchor="middle"
                  fill="rgba(226,232,240,0.82)"
                  fontSize="18"
                  letterSpacing="0.18em"
                  style={{ textTransform: "uppercase" }}
                >
                  {node.label}
                </text>
              </g>
            );
          })}

          {!prefersReduced && (
            <motion.circle
              r="5.2"
              fill="rgba(45,212,191,0.95)"
              stroke="rgba(125,211,252,0.72)"
              strokeWidth="1.1"
              initial={{
                cx: tickerNode.x,
                cy: tickerNode.y,
                opacity: 0,
              }}
              animate={{
                cx: [
                  tickerNode.x,
                  tickerNode.x,
                  relativeNode.x,
                  deckNode.x,
                  deckNode.x,
                  tickerNode.x,
                ],
                cy: [
                  tickerNode.y,
                  tickerNode.y,
                  relativeNode.y,
                  deckNode.y,
                  deckNode.y,
                  tickerNode.y,
                ],
                opacity: [0, 1, 1, 1, 0, 0],
              }}
              transition={{
                duration: CYCLE_SECONDS,
                ease: "linear",
                repeat: Infinity,
                times: [0, 0.03, 0.18, 0.37, 0.46, 1],
              }}
              style={{
                filter: "drop-shadow(0 0 5px rgba(45,212,191,0.45))",
              }}
            />
          )}
        </svg>
      </div>
    </div>
  );
}
