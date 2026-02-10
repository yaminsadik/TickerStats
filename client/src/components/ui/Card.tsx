import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../../utils/cn";

interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, "onClick"> {
  children: ReactNode;
  className?: string;
  padding?: "none" | "sm" | "md" | "lg";
  elevation?: "flat" | "raised" | "floating";
  interactive?: boolean;
  onClick?: () => void;
}

export default function Card({
  children,
  className,
  padding = "md",
  elevation = "flat",
  interactive = false,
  onClick,
  ...rest
}: CardProps) {
  const paddingStyles = {
    none: "",
    sm: "p-4",
    md: "p-6",
    lg: "p-8",
  };

  const elevationStyles = {
    flat: "border border-slate-800",
    raised: "border border-slate-800 shadow-md",
    floating: "border border-slate-700 shadow-xl shadow-black/20",
  };

  const interactiveStyles = interactive
    ? "cursor-pointer hover:border-slate-700 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200"
    : "";

  return (
    <div
      className={cn(
        "bg-slate-900 rounded-xl",
        paddingStyles[padding],
        elevationStyles[elevation],
        interactiveStyles,
        className,
      )}
      onClick={onClick}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick?.();
              }
            }
          : undefined
      }
      {...rest}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function CardHeader({ title, description, action }: CardHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-4">
      <div>
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        {description && (
          <p className="text-sm text-slate-400 mt-1">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}
