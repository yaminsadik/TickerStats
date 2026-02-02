import { cn } from "../../utils/cn";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

export default function Badge({
  children,
  variant = "default",
  className,
}: BadgeProps) {
  const variants: Record<BadgeVariant, string> = {
    default: "bg-slate-700 text-slate-300",
    success: "bg-green-900/50 text-green-400 border border-green-800",
    warning: "bg-yellow-900/50 text-yellow-400 border border-yellow-800",
    danger: "bg-red-900/50 text-red-400 border border-red-800",
    info: "bg-blue-900/50 text-blue-400 border border-blue-800",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
