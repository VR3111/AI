import { ConversationCompareMeta } from "../types/api";
import { GitCompareArrows, X } from "lucide-react";

interface CompareBannerProps {
  compare: ConversationCompareMeta;
  onClear?: () => void;
}

function joinLabels(labels: string[]) {
  if (labels.length <= 1) {
    return labels[0] || "Selected documents";
  }
  if (labels.length === 2) {
    return `${labels[0]} and ${labels[1]}`;
  }
  return `${labels.slice(0, -1).join(", ")}, and ${labels[labels.length - 1]}`;
}

function formatLabel(label: string) {
  const base = label
    .split("/")
    .pop()
    ?.replace(/\.[a-z0-9]+$/i, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!base) {
    return label;
  }

  return base
    .split(" ")
    .filter(Boolean)
    .map((word) => {
      if (/^[A-Z0-9]{2,6}$/.test(word)) {
        return word;
      }
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(" ");
}

export function CompareBanner({ compare, onClear }: CompareBannerProps) {
  const summary = joinLabels(compare.labels.map(formatLabel));

  return (
    <div className="flex items-start gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2.5 shadow-sm sm:items-center sm:rounded-2xl sm:px-4 sm:py-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-emerald-500/20 bg-emerald-500/10 text-emerald-300 sm:h-9 sm:w-9 sm:rounded-lg">
        <GitCompareArrows className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[9px] uppercase tracking-[0.16em] text-emerald-400 sm:text-[10px] sm:tracking-[0.18em]">
          Active Compare
        </div>
        <div className="mt-1 text-[13px] leading-5 text-foreground/90 sm:text-sm">
          Comparing: <span className="font-medium">{summary}</span>
        </div>
        {compare.field ? (
          <div className="mt-1 text-[11px] leading-4 text-muted-foreground sm:text-xs">
            Latest field: {compare.field}
          </div>
        ) : null}
      </div>
      <button
        type="button"
        onClick={onClear}
        className="inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-xl border border-border/50 bg-card/80 px-3 text-[11px] text-muted-foreground transition-colors hover:border-emerald-500/30 hover:text-foreground sm:min-h-0 sm:rounded-lg sm:px-2.5 sm:py-1.5 sm:text-xs"
      >
        <X className="h-3.5 w-3.5" />
        Clear
      </button>
    </div>
  );
}
