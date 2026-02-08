import { useRef, useEffect, useCallback, useState } from "react";

// ─── Tiny inline noise SVG ──────────────────────────────────────────────────
const NOISE_URI =
  "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNTAiIGhlaWdodD0iMjUwIj48ZmlsdGVyIGlkPSJuIj48ZmVUdXJidWxlbmNlIHR5cGU9ImZyYWN0YWxOb2lzZSIgYmFzZUZyZXF1ZW5jeT0iMC44IiBudW1PY3RhdmVzPSI0IiBzdGl0Y2hUaWxlcz0ic3RpdGNoIi8+PC9maWx0ZXI+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsdGVyPSJ1cmwoI24pIiBvcGFjaXR5PSIxIi8+PC9zdmc+";

/**
 * InteractiveHero — Auth0-style interactive hero background.
 *
 * Color cycling is 100% CSS keyframes (no JS state changes).
 * Cursor spotlight + tilt use rAF + CSS variables (no re-renders).
 */
export default function InteractiveHero({
  children,
}: {
  children: React.ReactNode;
}) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const rafId = useRef(0);
  const [isHovering, setIsHovering] = useState(false);
  const [prefersReduced, setPrefersReduced] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReduced(mql.matches);
    const handler = (e: MediaQueryListEvent) => setPrefersReduced(e.matches);
    mql.addEventListener("change", handler);

    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile, { passive: true });

    return () => {
      mql.removeEventListener("change", handler);
      window.removeEventListener("resize", checkMobile);
    };
  }, []);

  const shouldTrack = !prefersReduced && !isMobile;

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!shouldTrack) return;
      cancelAnimationFrame(rafId.current);
      rafId.current = requestAnimationFrame(() => {
        const el = wrapperRef.current;
        if (!el) return;
        const rect = el.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        el.style.setProperty("--mx", `${x}px`);
        el.style.setProperty("--my", `${y}px`);
        const cx = rect.width / 2;
        const cy = rect.height / 2;
        el.style.setProperty("--rotX", `${((cy - y) / cy) * 1.5}deg`);
        el.style.setProperty("--rotY", `${((x - cx) / cx) * 2}deg`);
      });
    },
    [shouldTrack],
  );

  const handleMouseEnter = useCallback(() => setIsHovering(true), []);
  const handleMouseLeave = useCallback(() => {
    setIsHovering(false);
    const el = wrapperRef.current;
    if (el) {
      el.style.setProperty("--rotX", "0deg");
      el.style.setProperty("--rotY", "0deg");
    }
  }, []);

  const animClass = prefersReduced ? "" : "hero-bg-cycle";

  return (
    <div
      ref={wrapperRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className="relative isolate overflow-hidden"
      style={
        {
          "--mx": "50%",
          "--my": "50%",
          "--rotX": "0deg",
          "--rotY": "0deg",
        } as React.CSSProperties
      }
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

      {/* 2. Orb A — center top */}
      <div
        className={`absolute z-0 top-[-5%] left-1/2 -translate-x-1/2 w-[700px] h-[700px] rounded-full blur-[140px] ${animClass}-orb-a`}
        aria-hidden="true"
      />
      {/* 3. Orb B — left */}
      <div
        className={`absolute z-0 top-[15%] left-[5%] w-[480px] h-[480px] rounded-full blur-[120px] ${animClass}-orb-b`}
        aria-hidden="true"
      />
      {/* 4. Orb C — right */}
      <div
        className={`absolute z-0 top-[15%] right-[5%] w-[420px] h-[420px] rounded-full blur-[110px] ${animClass}-orb-c`}
        aria-hidden="true"
      />

      {/* 5. Cursor spotlight */}
      {shouldTrack && (
        <div
          className={`absolute inset-0 z-0 pointer-events-none ${animClass}-spot`}
          aria-hidden="true"
          style={{
            opacity: isHovering ? 1 : 0,
            transition: "opacity 0.4s ease",
            background:
              "radial-gradient(600px circle at var(--mx) var(--my), var(--spot-color, rgba(99,102,241,0.18)), transparent 50%)",
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

      {/* Content with subtle tilt */}
      <div
        className="relative z-10"
        style={
          shouldTrack
            ? {
                transform:
                  "perspective(1200px) rotateX(var(--rotX)) rotateY(var(--rotY))",
                transition: "transform 0.15s ease-out",
                willChange: "transform",
              }
            : undefined
        }
      >
        {children}
      </div>
    </div>
  );
}
