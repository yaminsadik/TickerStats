import { AlertCircle, CheckCircle, Info, AlertTriangle, X } from "lucide-react";
import { cn } from "../../utils/cn";

type AlertVariant = "info" | "success" | "warning" | "error";

interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

export default function Alert({
  variant = "info",
  title,
  children,
  onDismiss,
  className,
}: AlertProps) {
  const variants: Record<
    AlertVariant,
    { bg: string; icon: typeof Info; iconColor: string }
  > = {
    info: {
      bg: "bg-blue-900/30 border-blue-800",
      icon: Info,
      iconColor: "text-blue-400",
    },
    success: {
      bg: "bg-green-900/30 border-green-800",
      icon: CheckCircle,
      iconColor: "text-green-400",
    },
    warning: {
      bg: "bg-yellow-900/30 border-yellow-800",
      icon: AlertTriangle,
      iconColor: "text-yellow-400",
    },
    error: {
      bg: "bg-red-900/30 border-red-800",
      icon: AlertCircle,
      iconColor: "text-red-400",
    },
  };

  const { bg, icon: Icon, iconColor } = variants[variant];

  return (
    <div className={cn("rounded-lg border p-4", bg, className)}>
      <div className="flex">
        <Icon className={cn("h-5 w-5 flex-shrink-0", iconColor)} />
        <div className="ml-3 flex-1">
          {title && <h3 className="text-sm font-medium text-white">{title}</h3>}
          <div className={cn("text-sm text-slate-300", title && "mt-1")}>
            {children}
          </div>
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="ml-3 flex-shrink-0 text-slate-400 hover:text-slate-300"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>
    </div>
  );
}
