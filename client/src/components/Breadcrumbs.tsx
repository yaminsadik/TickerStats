import { Fragment, ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";
import { cn } from "../utils/cn";

interface BreadcrumbItemProps {
  href?: string;
  children: ReactNode;
  current?: boolean;
}

export function BreadcrumbItem({ href, children, current = false }: BreadcrumbItemProps) {
  if (current || !href) {
    return (
      <span
        className="text-sm font-medium text-white"
        aria-current={current ? "page" : undefined}
      >
        {children}
      </span>
    );
  }

  return (
    <Link
      to={href}
      className="text-sm font-medium text-slate-400 hover:text-white transition-colors"
    >
      {children}
    </Link>
  );
}

interface BreadcrumbsProps {
  children: ReactNode;
  className?: string;
}

export default function Breadcrumbs({ children, className }: BreadcrumbsProps) {
  const items = Array.isArray(children) ? children : [children];

  return (
    <nav
      aria-label="Breadcrumb"
      className={cn("flex items-center space-x-2 mb-6", className)}
    >
      <ol className="flex items-center space-x-2">
        {/* Home icon */}
        <li>
          <Link
            to="/"
            className="text-slate-400 hover:text-white transition-colors"
            aria-label="Home"
          >
            <Home className="w-4 h-4" />
          </Link>
        </li>

        {items.map((item, index) => (
          <Fragment key={index}>
            <li>
              <ChevronRight className="w-4 h-4 text-slate-600" aria-hidden="true" />
            </li>
            <li>{item}</li>
          </Fragment>
        ))}
      </ol>
    </nav>
  );
}

export { Breadcrumbs };
