import { useRef, useEffect, useCallback, useState } from "react";
import {
  motion,
  useMotionTemplate,
  useMotionValue,
  useReducedMotion,
  useSpring,
} from "framer-motion";
import MarketOverlay from "./MarketOverlay";

// ─── Tiny inline noise SVG ──────────────────────────────────────────────────
const NOISE_URI =
  "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNTAiIGhlaWdodD0iMjUwIj48ZmlsdGVyIGlkPSJuIj48ZmVUdXJidWxlbmNlIHR5cGU9ImZyYWN0YWxOb2lzZSIgYmFzZUZyZXF1ZW5jeT0iMC44IiBudW1PY3RhdmVzPSI0IiBzdGl0Y2hUaWxlcz0ic3RpdGNoIi8+PC9maWx0ZXI+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsdGVyPSJ1cmwoI24pIiBvcGFjaXR5PSIxIi8+PC9zdmc+";

/**
 * InteractiveHero: Auth0-style interactive hero background.
 *
 * Color cycling is 100% CSS keyframes (no JS state changes).
 * Cursor spotlight + tilt are driven by Framer Motion values.
 */
export default function InteractiveHero({
  children,
}: {
  children: React.ReactNode;
}) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [isHovering, setIsHovering] = useState(false);
  const [canTrackPointer, setCanTrackPointer] = useState(false);
  const prefersReduced = useReducedMotion() ?? false;
  const rotateX = useMotionValue(0);
  const rotateY = useMotionValue(0);
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const smoothRotateX = useSpring(rotateX, {
    stiffness: 120,
    damping: 34,
    mass: 0.7,
  });
  const smoothRotateY = useSpring(rotateY, {
    stiffness: 120,
    damping: 34,
    mass: 0.7,
  });
  const smoothMouseX = useSpring(mouseX, {
    stiffness: 52,
    damping: 28,
    mass: 1,
  });
  const smoothMouseY = useSpring(mouseY, {
    stiffness: 52,
    damping: 28,
    mass: 1,
  });
  const spotBackground = useMotionTemplate`radial-gradient(780px circle at ${smoothMouseX}px ${smoothMouseY}px, var(--spot-color, rgba(125,211,252,0.10)), transparent 62%)`;

  useEffect(() => {
    const pointerQuery = window.matchMedia("(hover: hover) and (pointer: fine)");
    const setTracking = (pointerMatch: boolean) => {
      setCanTrackPointer(pointerMatch && window.innerWidth >= 768);
    };
    const onPointerChange = (e: MediaQueryListEvent) => setTracking(e.matches);
    const setSpotCenter = () => {
      const el = wrapperRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      mouseX.set(rect.width / 2);
      mouseY.set(rect.height / 2);
    };
    const onResize = () => {
      setTracking(pointerQuery.matches);
      setSpotCenter();
    };
    setTracking(pointerQuery.matches);
    setSpotCenter();
    pointerQuery.addEventListener("change", onPointerChange);
    window.addEventListener("resize", onResize, { passive: true });

    return () => {
      pointerQuery.removeEventListener("change", onPointerChange);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  const shouldTrack = !prefersReduced && canTrackPointer;

  useEffect(() => {
    if (shouldTrack) return;
    rotateX.set(0);
    rotateY.set(0);
    setIsHovering(false);
  }, [rotateX, rotateY, shouldTrack]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!shouldTrack) return;
      const el = wrapperRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      mouseX.set(x);
      mouseY.set(y);
      const cx = rect.width / 2 || 1;
      const cy = rect.height / 2 || 1;
      rotateX.set(((cy - y) / cy) * 1.5);
      rotateY.set(((x - cx) / cx) * 2);
    },
    [mouseX, mouseY, rotateX, rotateY, shouldTrack],
  );

  const handleMouseEnter = useCallback(() => setIsHovering(true), []);
  const handleMouseLeave = useCallback(() => {
    setIsHovering(false);
    rotateX.set(0);
    rotateY.set(0);
  }, [rotateX, rotateY]);

  const animClass = prefersReduced ? "" : "hero-bg-cycle";

  return (
    <div
      ref={wrapperRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className="relative isolate overflow-hidden"
    >
      {/* 1. Base gradient with color cycle */}
      <div
        className={`absolute inset-0 z-0 ${animClass}`}
        aria-hidden="true"
        style={{
          background: prefersReduced
            ? "linear-gradient(to bottom, rgba(30,58,138,0.35), #020617 60%)"
            : undefined,
        }}
      />

      {/* 2. Orb A - center top */}
      <div
        className={`absolute z-0 top-[-5%] left-1/2 -translate-x-1/2 w-[700px] h-[700px] rounded-full blur-[140px] ${animClass}-orb-a`}
        aria-hidden="true"
      />
      {/* 3. Orb B - left */}
      <div
        className={`absolute z-0 top-[15%] left-[5%] w-[480px] h-[480px] rounded-full blur-[120px] ${animClass}-orb-b`}
        aria-hidden="true"
      />
      {/* 4. Orb C - right */}
      <div
        className={`absolute z-0 top-[15%] right-[5%] w-[420px] h-[420px] rounded-full blur-[110px] ${animClass}-orb-c`}
        aria-hidden="true"
      />

      {/* 5. Cursor spotlight */}
      {shouldTrack && (
        <motion.div
          className={`absolute inset-0 z-0 pointer-events-none ${animClass}-spot`}
          aria-hidden="true"
          animate={{ opacity: isHovering ? 0.45 : 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          style={{
            background: spotBackground,
          }}
        />
      )}

      {/* 6. Grid overlay */}
      <div
        className="absolute inset-0 z-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_70%_55%_at_50%_0%,#000_45%,transparent_100%)] opacity-[0.15] pointer-events-none"
        aria-hidden="true"
      />

      {/* 7. Noise overlay */}
      <div
        className="absolute inset-0 z-0 opacity-[0.035] mix-blend-overlay pointer-events-none"
        aria-hidden="true"
        style={{
          backgroundImage: `url("${NOISE_URI}")`,
          backgroundRepeat: "repeat",
        }}
      />

      {/* 8. Finance market scene */}
      <MarketOverlay prefersReduced={prefersReduced} />

      {/* Content with subtle tilt */}
      <motion.div
        className="relative z-10"
        style={
          shouldTrack
            ? {
                transformPerspective: 1200,
                rotateX: smoothRotateX,
                rotateY: smoothRotateY,
                willChange: "transform",
              }
            : undefined
        }
      >
        {children}
      </motion.div>
    </div>
  );
}
