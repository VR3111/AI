import { useEffect, useMemo, useState } from "react";
import {
  ArrowRightLeft,
  CheckCircle2,
  FileText,
  Sparkles,
} from "lucide-react";

import {
  ComparePickerCandidate,
  ComparePickerSide,
  ComparePickerState,
  Document,
  QuerySubmitOptions,
} from "../types/api";
import { Button } from "./ui/button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
} from "./ui/select";
import { cn } from "./ui/utils";

interface ComparePickerProps {
  picker: ComparePickerState;
  documents: Document[];
  query: string;
  compareFocusQuery?: string;
  onSubmitQuery?: (query: string, options?: QuerySubmitOptions) => Promise<void>;
  isProcessing?: boolean;
}

type CompareOption = {
  source: string;
  label: string;
};

function readableLabel(label: string) {
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
    .map((word) =>
      /^[A-Z0-9]{2,6}$/.test(word)
        ? word
        : `${word[0]?.toUpperCase() || ""}${word.slice(1).toLowerCase()}`,
    )
    .join(" ");
}

function compareOptionFromCandidate(candidate: ComparePickerCandidate): CompareOption {
  return {
    source: candidate.source,
    label: readableLabel(candidate.display_name || candidate.source),
  };
}

function suggestionTone(confidence?: ComparePickerSide["confidence"]) {
  if (confidence === "high") {
    return {
      badge: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
      iconWrap: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
      panel: "border-emerald-500/18 bg-emerald-500/[0.05]",
      trigger:
        "border-emerald-500/22 bg-emerald-500/[0.06] hover:border-emerald-500/35 focus-visible:border-emerald-500/40",
      meta: "text-emerald-300/90",
      label: "Resolved",
    };
  }

  return {
    badge: "border-amber-500/25 bg-amber-500/10 text-amber-200",
    iconWrap: "border-amber-500/20 bg-amber-500/10 text-amber-200",
    panel: "border-border/45 bg-card/60",
    trigger:
      "border-border/55 bg-background/70 hover:border-amber-500/28 focus-visible:border-amber-500/35",
    meta: "text-amber-200/90",
    label: confidence ? "Suggested" : "Select",
  };
}

function CompareDocumentField({
  title,
  source,
  onChange,
  suggestion,
  suggestedOptions,
  allOptions,
}: {
  title: string;
  source: string;
  onChange: (value: string) => void;
  suggestion?: ComparePickerSide | null;
  suggestedOptions: CompareOption[];
  allOptions: CompareOption[];
}) {
  const tone = suggestionTone(suggestion?.confidence);
  const selectedLabel =
    [...suggestedOptions, ...allOptions].find((option) => option.source === source)?.label ??
    "";

  return (
    <div className={cn("rounded-[18px] border px-3 py-3", tone.panel)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground/85">
            {title}
          </div>
          {suggestion?.matched_alias ? (
            <div className={cn("mt-1 text-[11px] leading-4", tone.meta)}>
              Matched from “{suggestion.matched_alias}”
            </div>
          ) : (
            <div className="mt-1 text-[11px] leading-4 text-muted-foreground">
              Pick from suggested matches or the full document list.
            </div>
          )}
        </div>
        <span
          className={cn(
            "inline-flex min-h-6 shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium tracking-wide",
            tone.badge,
          )}
        >
          {suggestion?.confidence === "high" ? (
            <CheckCircle2 className="h-3 w-3" />
          ) : (
            <Sparkles className="h-3 w-3" />
          )}
          {tone.label}
        </span>
      </div>

      <Select value={source} onValueChange={onChange}>
        <SelectTrigger
          className={cn(
            "relative mt-3 h-auto min-h-[54px] rounded-2xl px-3.5 py-3 pr-10 shadow-sm ring-0 [&>svg]:absolute [&>svg]:right-3.5 [&>svg]:top-1/2 [&>svg]:-translate-y-1/2 [&>svg]:opacity-75",
            tone.trigger,
          )}
        >
          <div className="flex min-w-0 items-center gap-3 pr-2">
            <div
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border",
                tone.iconWrap,
              )}
            >
              <FileText className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0 flex-1 text-left">
              <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground/80">
                Selected document
              </div>
              <div
                className={cn(
                  "mt-1 truncate text-sm font-medium leading-5",
                  selectedLabel ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {selectedLabel || "Choose a document"}
              </div>
            </div>
          </div>
        </SelectTrigger>
        <SelectContent className="rounded-2xl border-border/50 bg-popover/95 p-1.5 shadow-2xl backdrop-blur-xl">
          {suggestedOptions.length > 0 ? (
            <SelectGroup>
              <SelectLabel className="px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-emerald-300/80">
                Suggested For This Compare
              </SelectLabel>
              {suggestedOptions.map((option) => (
                <SelectItem
                  key={option.source}
                  value={option.source}
                  className="rounded-xl px-3 py-2.5 text-sm"
                >
                  {option.label}
                </SelectItem>
              ))}
            </SelectGroup>
          ) : null}

          {suggestedOptions.length > 0 && allOptions.length > 0 ? (
            <SelectSeparator className="mx-1 my-1.5" />
          ) : null}

          <SelectGroup>
            <SelectLabel className="px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground/80">
              All Uploaded Documents
            </SelectLabel>
            {allOptions.map((option) => (
              <SelectItem
                key={option.source}
                value={option.source}
                className="rounded-xl px-3 py-2.5 text-sm"
              >
                {option.label}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
}

export function ComparePicker({
  picker,
  documents,
  query,
  compareFocusQuery,
  onSubmitQuery,
  isProcessing = false,
}: ComparePickerProps) {
  const [leftSource, setLeftSource] = useState(picker.left?.source ?? "");
  const [rightSource, setRightSource] = useState(picker.right?.source ?? "");

  useEffect(() => {
    setLeftSource(picker.left?.source ?? "");
    setRightSource(picker.right?.source ?? "");
  }, [picker.left?.source, picker.right?.source, query]);

  const suggestedOptions = useMemo(() => {
    const merged = new Map<string, CompareOption>();
    for (const candidate of picker.candidates ?? []) {
      merged.set(candidate.source, compareOptionFromCandidate(candidate));
    }
    return Array.from(merged.values());
  }, [picker.candidates]);

  const allOptions = useMemo(() => {
    const suggestedSources = new Set(suggestedOptions.map((option) => option.source));
    const merged = new Map<string, CompareOption>();

    for (const document of documents) {
      if (!suggestedSources.has(document.source)) {
        merged.set(document.source, {
          source: document.source,
          label: readableLabel(document.filename || document.source),
        });
      }
    }

    for (const side of [picker.left, picker.right]) {
      if (side?.source && !suggestedSources.has(side.source) && !merged.has(side.source)) {
        merged.set(side.source, {
          source: side.source,
          label: readableLabel(side.display_name || side.source),
        });
      }
    }

    return Array.from(merged.values()).sort((left, right) =>
      left.label.localeCompare(right.label),
    );
  }, [documents, picker.left, picker.right, suggestedOptions]);

  const canSubmit =
    Boolean(picker.can_submit) &&
    Boolean(leftSource) &&
    Boolean(rightSource) &&
    leftSource !== rightSource &&
    !isProcessing &&
    Boolean(onSubmitQuery);

  const handleCompare = async () => {
    if (!canSubmit || !onSubmitQuery) {
      return;
    }

    await onSubmitQuery(query, {
      compareSources: [leftSource, rightSource],
      compareFocusQuery,
      workspaceScope: "global",
    });
  };

  return (
    <div className="mt-3 rounded-[22px] border border-emerald-500/16 bg-gradient-to-br from-emerald-500/[0.08] via-background/85 to-background/70 p-3 shadow-[0_10px_30px_-18px_rgba(16,185,129,0.35)] backdrop-blur-sm sm:p-3.5">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-emerald-500/20 bg-emerald-500/10 text-emerald-300">
          <ArrowRightLeft className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-medium uppercase tracking-[0.18em] text-emerald-300/85">
            Compare Picker
          </div>
          <div className="mt-1 text-[13px] leading-5 text-foreground/90 sm:text-sm">
            Confirm both documents, or swap either side from your uploaded list.
          </div>
        </div>
      </div>

      <div className="mt-3 grid gap-2.5">
        <CompareDocumentField
          title="First document"
          source={leftSource}
          onChange={setLeftSource}
          suggestion={picker.left ?? null}
          suggestedOptions={suggestedOptions}
          allOptions={allOptions}
        />
        <CompareDocumentField
          title="Second document"
          source={rightSource}
          onChange={setRightSource}
          suggestion={picker.right ?? null}
          suggestedOptions={suggestedOptions}
          allOptions={allOptions}
        />
      </div>

      <div className="mt-3 grid gap-2.5 border-t border-white/6 pt-3 sm:grid-cols-[1fr_auto] sm:items-center">
        <div className="text-[11px] leading-4 text-muted-foreground">
          {picker.can_submit
            ? "Compare runs only after both document choices are confirmed."
            : "Choose two documents first, then ask for one field like annual fee or APR."}
        </div>
        <Button
          type="button"
          onClick={() => void handleCompare()}
          disabled={!canSubmit}
          className="h-10 rounded-xl bg-emerald-500/90 px-4 text-sm font-medium text-emerald-950 shadow-sm hover:bg-emerald-400"
        >
          Compare
        </Button>
      </div>
    </div>
  );
}
