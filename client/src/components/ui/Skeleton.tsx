import { cn } from "../../utils/cn";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-slate-800/50",
        className
      )}
      aria-hidden="true"
    />
  );
}

interface TableSkeletonProps {
  rows?: number;
  cols?: number;
}

export function TableSkeleton({ rows = 5, cols = 8 }: TableSkeletonProps) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading table">
      {/* Header skeleton */}
      <div className="h-12 bg-slate-800 rounded-lg" />
      
      {/* Row skeletons */}
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="grid gap-4 p-4 bg-slate-800/30 rounded-lg"
          style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
        >
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className="h-6" />
          ))}
        </div>
      ))}
      <span className="sr-only">Loading table data...</span>
    </div>
  );
}

interface CardSkeletonProps {
  count?: number;
}

export function CardSkeleton({ count = 1 }: CardSkeletonProps) {
  return (
    <div className="space-y-4" role="status" aria-label="Loading content">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-slate-900 border border-slate-800 rounded-lg p-6">
          <Skeleton className="h-6 w-1/3 mb-4" />
          <Skeleton className="h-4 w-full mb-2" />
          <Skeleton className="h-4 w-5/6 mb-2" />
          <Skeleton className="h-4 w-4/6" />
        </div>
      ))}
      <span className="sr-only">Loading cards...</span>
    </div>
  );
}

interface SectionSkeletonProps {
  count?: number;
}

export function SectionSkeleton({ count = 3 }: SectionSkeletonProps) {
  return (
    <div className="space-y-4" role="status" aria-label="Loading sections">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <Skeleton className="h-7 w-48" />
            <Skeleton className="h-10 w-32" />
          </div>
          <div className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-11/12" />
            <Skeleton className="h-4 w-10/12" />
            <Skeleton className="h-4 w-9/12" />
          </div>
        </div>
      ))}
      <span className="sr-only">Loading sections...</span>
    </div>
  );
}

export default Skeleton;
