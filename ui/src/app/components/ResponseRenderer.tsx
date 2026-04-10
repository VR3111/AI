import {
  CompareResultItem,
  Document,
  MatchedDocumentOption,
  QueryResponse,
  QuerySubmitOptions,
} from "../types/api";
import { Tooltip } from "./Tooltip";
import { useMemo, useState } from "react";
import { ComparePicker } from "./ComparePicker";

interface ResponseRendererProps {
  response: QueryResponse;
  documents?: Document[];
  submittedQuery?: string;
  onSubmitQuery?: (query: string, options?: QuerySubmitOptions) => Promise<void>;
  isProcessing?: boolean;
  showComparePicker?: boolean;
}

function getFilenameFromSource(source?: string) {
  if (!source) return "Unknown source";
  const parts = source.split("/");
  return parts[parts.length - 1] || source;
}

function getReadableDocumentName(documentName: string) {
  const filename = getFilenameFromSource(documentName).replace(/\.[a-z0-9]+$/i, "");
  const normalized = filename
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  const noiseTokens = new Set(["final", "draft", "copy", "signed"]);
  const words = normalized.split(" ").filter(Boolean);

  while (words.length > 1) {
    const lastWord = words[words.length - 1];
    if (
      /^\d{1,8}$/.test(lastWord) ||
      /^v\d+$/i.test(lastWord) ||
      noiseTokens.has(lastWord.toLowerCase())
    ) {
      words.pop();
      continue;
    }
    break;
  }

  return words
    .map((word) => {
      if (/^[A-Z0-9]{2,5}$/.test(word)) return word;
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(" ")
    .trim();
}

function getCompareDocumentTitle(item: CompareResultItem) {
  return getReadableDocumentName(item.display_name || item.source);
}

function getCompareValue(item: CompareResultItem) {
  return item.found ? item.value || "" : "Not explicitly found";
}

function isCompactCompareValue(value: string) {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length > 0 && normalized.length <= 24 && !normalized.includes("\n");
}

export function ResponseRenderer({
  response,
  documents = [],
  submittedQuery,
  onSubmitQuery,
  isProcessing = false,
  showComparePicker = true,
}: ResponseRendererProps) {
  const [citationsOpen, setCitationsOpen] = useState(false);

  const hasCitations = !!response.citations && response.citations.length > 0;
  const compareResults: CompareResultItem[] = response.artifacts?.compare_results ?? [];
  const isCompareResult =
    response.mode === "direct_answer" &&
    response.artifacts?.reason === "compare_result" &&
    compareResults.length > 0;
  const matchedDocuments: MatchedDocumentOption[] =
    response.artifacts?.matched_document_options?.map((option) => ({
      source: option.source,
      display_name: getReadableDocumentName(option.display_name || option.source),
    })) ??
    (response.artifacts?.matched_documents ?? []).map((documentName) => ({
      source: "",
      display_name: getReadableDocumentName(documentName),
    }));
  const showsMatchedDocuments =
    response.mode === "guided_fallback" &&
    response.artifacts?.reason === "multiple_documents_match" &&
    matchedDocuments.length > 0;
  const comparePicker = response.artifacts?.compare_picker;
  const showsComparePicker =
    showComparePicker &&
    response.artifacts?.reason === "compare_picker" &&
    Boolean(comparePicker);

  const accent = useMemo(() => {
    if (response.mode === "direct_answer") return "emerald";
    if (response.mode === "guided_fallback") return "amber";
    return "zinc";
  }, [response.mode]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const getCopyButtonClass = (tone: "emerald" | "amber" | "zinc") => {
    const toneClasses =
      tone === "emerald"
        ? "hover:border-emerald-500/50 hover:bg-emerald-500/10"
        : tone === "amber"
        ? "hover:border-amber-500/50 hover:bg-amber-500/10"
        : "hover:border-zinc-500/50 hover:bg-zinc-500/10";

    return `inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border/50 bg-card/80 backdrop-blur-sm opacity-100 transition-all duration-150 lg:opacity-0 lg:group-hover:opacity-100 ${toneClasses}`;
  };

  const getCopyIconClass = (tone: "emerald" | "amber" | "zinc") => {
    return tone === "emerald"
      ? "w-3.5 h-3.5 text-muted-foreground hover:text-emerald-400"
      : tone === "amber"
      ? "w-3.5 h-3.5 text-muted-foreground hover:text-amber-400"
      : "w-3.5 h-3.5 text-muted-foreground hover:text-zinc-300";
  };

  const handleMatchedDocumentClick = async (document: MatchedDocumentOption) => {
    if (!submittedQuery || !onSubmitQuery || !document.source || isProcessing) return;
    await onSubmitQuery(submittedQuery, {
      selectedSource: document.source,
      selectedSourceLabel: document.display_name,
      activateScope: true,
      workspaceScope: "global",
    });
  };

  const renderCitations = () => {
    if (!hasCitations) return null;

    const border =
      accent === "emerald"
        ? "border-emerald-500/10"
        : accent === "amber"
        ? "border-amber-500/10"
        : "border-zinc-500/10";

    const hoverBorder =
      accent === "emerald"
        ? "hover:border-emerald-500/30"
        : accent === "amber"
        ? "hover:border-amber-500/30"
        : "hover:border-zinc-500/30";

    const hoverIcon =
      accent === "emerald"
        ? "group-hover:text-emerald-500"
        : accent === "amber"
        ? "group-hover:text-amber-500"
        : "group-hover:text-zinc-300";

    const chipBg =
      accent === "emerald"
        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
        : accent === "amber"
        ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
        : "bg-zinc-500/10 text-zinc-300 border-zinc-500/20";

    return (
      <div className={`border-t ${border} pt-3 lg:pt-4 mt-3 lg:mt-4`}>
        <button
          type="button"
          onClick={() => setCitationsOpen((v) => !v)}
          className="w-full flex items-center justify-between gap-3 text-left"
        >
          <div className="text-[10px] lg:text-xs text-muted-foreground uppercase tracking-wider">
            Source Citations
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`text-[10px] lg:text-xs px-2 py-0.5 rounded-md border ${chipBg}`}
            >
              {response.citations.length}
            </span>

            <svg
              className={`w-4 h-4 text-muted-foreground transition-transform duration-200 ${
                citationsOpen ? "rotate-180" : "rotate-0"
              }`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </div>
        </button>

        <div
          className={`grid transition-all duration-200 ease-out ${
            citationsOpen ? "grid-rows-[1fr] opacity-100 mt-2 lg:mt-3" : "grid-rows-[0fr] opacity-0 mt-0"
          }`}
        >
          <div className="overflow-hidden">
            <div className="space-y-1.5 lg:space-y-2">
              {response.citations.map((citation, idx) => {
                const filename = getFilenameFromSource(citation.source);
                const pageLabel =
                  typeof citation.page === "number"
                    ? `Page ${citation.page}`
                    : "Page ?";

                return (
                  <div
                    key={idx}
                    className={`flex items-center gap-2 lg:gap-3 text-xs lg:text-sm bg-card/50 backdrop-blur-sm rounded-lg lg:rounded-xl px-3 lg:px-4 py-2 lg:py-2.5 border border-border/50 ${hoverBorder} transition-colors group`}
                    title={citation.snippet || ""}
                  >
                    <svg
                      className={`w-3 h-3 lg:w-4 lg:h-4 text-muted-foreground ${hoverIcon} flex-shrink-0 transition-colors`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>

                    <span className="flex-1 truncate text-foreground/90">
                      {filename}
                    </span>

                    <span className="text-muted-foreground text-[10px] lg:text-xs px-1.5 lg:px-2 py-0.5 lg:py-1 bg-secondary/50 rounded">
                      {pageLabel}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderCompareResults = () => {
    if (!isCompareResult) return null;

    return (
      <div className="mb-2.5 lg:mb-3.5">
        {response.artifacts?.compare_field && (
          <div className="mb-2 text-[10px] lg:mb-2.5 lg:text-xs uppercase tracking-[0.18em] text-emerald-400/90">
            Comparing {response.artifacts.compare_field}
          </div>
        )}

        <div className="grid gap-2.5 lg:gap-3">
          {compareResults.map((item) => {
            const title = getCompareDocumentTitle(item);
            const value = getCompareValue(item);
            const compactValue = isCompactCompareValue(value);

            return (
              <div
                key={item.source || item.display_name}
                className="overflow-hidden rounded-xl lg:rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 via-emerald-500/[0.07] to-transparent"
              >
                <div className="flex items-start justify-between gap-2.5 border-b border-emerald-500/10 px-3 py-2.5 sm:px-3.5 lg:px-4 lg:py-3">
                  <div className="min-w-0">
                    <div className="text-[10px] lg:text-xs uppercase tracking-[0.18em] text-emerald-400/80">
                      Document
                    </div>
                    <div className="mt-1 text-sm lg:text-base font-medium leading-snug text-foreground">
                      {title}
                    </div>
                  </div>
                  <span
                    className={`inline-flex shrink-0 items-center rounded-full border px-2 py-1 text-[10px] lg:text-xs tracking-wide ${
                      item.found
                        ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                        : "border-zinc-500/20 bg-zinc-500/10 text-zinc-300"
                    }`}
                  >
                    {item.found ? "Found" : "Not Found"}
                  </span>
                </div>

                <div className="px-3 py-3 sm:px-3.5 sm:py-3.5 lg:px-4 lg:py-4">
                  <div className="text-[10px] lg:text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    Value
                  </div>
                  <div className="mt-2">
                    {compactValue ? (
                      <div className="inline-flex max-w-full items-center rounded-xl border border-emerald-500/20 bg-background/70 px-2.5 py-1.5 text-sm lg:text-base font-medium text-foreground shadow-sm">
                        <span className="break-words">{value}</span>
                      </div>
                    ) : (
                      <div className="rounded-xl border border-border/40 bg-background/60 px-3 py-2.5 text-sm lg:text-base leading-relaxed text-foreground whitespace-pre-wrap break-words">
                        {value}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  // -----------------------------
  // DIRECT ANSWER
  // -----------------------------
  if (response.mode === "direct_answer") {
    return (
      <div
        className="relative bg-gradient-to-br from-emerald-500/10 via-emerald-500/5 to-transparent rounded-xl lg:rounded-2xl p-3 sm:p-4 lg:p-6 border border-emerald-500/20 shadow-lg backdrop-blur-sm group"
      >
        <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent rounded-lg lg:rounded-2xl pointer-events-none" />

        <div className="flex items-start gap-2.5 lg:gap-4 relative">
          <div className="flex-shrink-0 mt-0.5">
            <Tooltip content="Answer found directly in documents">
              <div className="w-6.5 h-6.5 flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-600 shadow-lg shadow-emerald-500/25 lg:h-8 lg:w-8 lg:rounded-xl">
                <svg
                  className="h-3.5 w-3.5 text-white lg:h-4 lg:w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2.5}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
            </Tooltip>
          </div>

          <div className="flex-1 min-w-0">
            <div className="mb-2 flex items-start justify-between gap-2.5 lg:mb-3 lg:gap-3">
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-400 backdrop-blur-sm lg:px-3 lg:py-1 lg:text-xs">
                <svg
                  className="w-2 h-2 lg:w-3 lg:h-3"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <span className="tracking-wide uppercase">
                  {isCompareResult ? "Compare" : "Direct Answer"}
                </span>
              </span>

              <button
                type="button"
                onClick={() => copyToClipboard(response.answer)}
                className={getCopyButtonClass("emerald")}
                aria-label="Copy answer"
              >
                <svg
                  className={getCopyIconClass("emerald")}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
              </button>
            </div>

            <div>
              {isCompareResult ? (
                renderCompareResults()
              ) : (
                <>
                  <div className="mb-2.5 whitespace-pre-wrap text-[14px] leading-6 text-foreground lg:mb-4 lg:text-base lg:leading-relaxed">
                    {response.answer}
                  </div>
                  {showsComparePicker && submittedQuery && (
                    <ComparePicker
                      picker={comparePicker!}
                      documents={documents}
                      query={submittedQuery}
                      compareFocusQuery={response.artifacts?.compare_focus_query}
                      onSubmitQuery={onSubmitQuery}
                      isProcessing={isProcessing}
                    />
                  )}
                </>
              )}
            </div>

            {renderCitations()}
          </div>
        </div>
      </div>
    );
  }

  // -----------------------------
  // GUIDED FALLBACK
  // -----------------------------
  if (response.mode === "guided_fallback") {
    return (
      <div
        className="relative bg-gradient-to-br from-amber-500/10 via-amber-500/5 to-transparent rounded-xl lg:rounded-2xl p-3 sm:p-4 lg:p-6 border border-amber-500/20 shadow-lg backdrop-blur-sm group"
      >
        <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent rounded-lg lg:rounded-2xl pointer-events-none" />

        <div className="flex items-start gap-2.5 lg:gap-4 relative">
          <div className="flex-shrink-0 mt-0.5">
            <Tooltip content="Guidance provided when answer not found verbatim">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-amber-500 to-amber-600 shadow-lg shadow-amber-500/25 lg:h-8 lg:w-8 lg:rounded-xl">
                <svg
                  className="w-3.5 h-3.5 lg:w-4 lg:h-4 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2.5}
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
            </Tooltip>
          </div>

          <div className="flex-1 min-w-0">
            <div className="mb-2 flex items-start justify-between gap-2.5 lg:mb-3 lg:gap-3">
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/20 px-2 py-0.5 text-[10px] text-amber-400 backdrop-blur-sm lg:px-3 lg:py-1 lg:text-xs">
                <svg
                  className="w-2 h-2 lg:w-3 lg:h-3"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <span className="tracking-wide uppercase">Guided Fallback</span>
              </span>

              <button
                type="button"
                onClick={() => copyToClipboard(response.answer)}
                className={getCopyButtonClass("amber")}
                aria-label="Copy guidance"
              >
                <svg
                  className={getCopyIconClass("amber")}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
              </button>
            </div>

            <div className="whitespace-pre-wrap text-[14px] leading-6 text-foreground lg:text-base lg:leading-relaxed">
              {response.answer}
            </div>

            {showsMatchedDocuments && (
              <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-2.5 sm:p-3.5 lg:mt-4.5 lg:p-4">
                <div className="mb-2 sm:mb-2.5">
                  <div className="mb-1 text-[10px] uppercase tracking-wider text-amber-400 lg:mb-1.5 lg:text-xs">
                    Multiple Matches
                  </div>
                  <p className="text-[14px] leading-6 text-foreground lg:text-base lg:leading-relaxed">
                    I found multiple matching documents. Choose one to continue, or compare them.
                  </p>
                </div>
                <div className="mt-2.5 grid gap-2">
                  {matchedDocuments.map((document) => (
                    <button
                      key={document.source || document.display_name}
                      type="button"
                      onClick={() => handleMatchedDocumentClick(document)}
                      disabled={!submittedQuery || !onSubmitQuery || !document.source || isProcessing}
                      className="w-full min-h-11 flex flex-col items-start gap-1.5 rounded-xl border border-border/50 bg-card/60 px-3 py-2.5 text-left transition-colors hover:border-amber-500/30 hover:bg-amber-500/10 disabled:cursor-not-allowed disabled:opacity-60 sm:min-h-0 sm:flex-row sm:items-center sm:justify-between sm:gap-3 sm:px-3 sm:py-3"
                    >
                      <span className="w-full min-w-0 truncate text-[14px] text-foreground/90 sm:flex-1 sm:pr-3 lg:text-base">
                        {document.display_name}
                      </span>
                      <span className="inline-flex items-center rounded-md border border-amber-500/20 bg-amber-500/10 px-2 py-1 text-[10px] lg:text-xs text-amber-400 tracking-wide self-start sm:self-auto whitespace-nowrap">
                        Ask in this doc
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {showsComparePicker && submittedQuery && (
              <ComparePicker
                picker={comparePicker!}
                documents={documents}
                query={submittedQuery}
                compareFocusQuery={response.artifacts?.compare_focus_query}
                onSubmitQuery={onSubmitQuery}
                isProcessing={isProcessing}
              />
            )}

            {renderCitations()}
          </div>
        </div>
      </div>
    );
  }

  // -----------------------------
  // HARD REFUSAL
  // -----------------------------
  if (response.mode === "hard_refusal") {
    return (
      <div
        className="relative bg-gradient-to-br from-zinc-500/10 via-zinc-500/5 to-transparent rounded-xl lg:rounded-2xl p-3 sm:p-4 lg:p-6 border border-zinc-500/20 shadow-lg backdrop-blur-sm group"
      >
        <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent rounded-lg lg:rounded-2xl pointer-events-none" />

        <div className="flex items-start gap-2.5 lg:gap-4 relative">
          <div className="flex-shrink-0 mt-0.5">
            <Tooltip content="Query cannot be answered from documents">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-zinc-600 to-zinc-700 shadow-lg shadow-zinc-500/25 lg:h-8 lg:w-8 lg:rounded-xl">
                <svg
                  className="w-3.5 h-3.5 lg:w-4 lg:h-4 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2.5}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </div>
            </Tooltip>
          </div>

          <div className="flex-1 min-w-0">
            <div className="mb-2 flex items-start justify-between gap-2.5 lg:mb-3 lg:gap-3">
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-500/30 bg-zinc-500/20 px-2 py-0.5 text-[10px] text-zinc-400 backdrop-blur-sm lg:px-3 lg:py-1 lg:text-xs">
                <svg
                  className="w-2 h-2 lg:w-3 lg:h-3"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <span className="tracking-wide uppercase">Hard Refusal</span>
              </span>

              <button
                type="button"
                onClick={() => copyToClipboard(response.answer)}
                className={getCopyButtonClass("zinc")}
                aria-label="Copy reason"
              >
                <svg
                  className={getCopyIconClass("zinc")}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
              </button>
            </div>

            <div className="whitespace-pre-wrap text-[14px] leading-6 text-foreground lg:text-base lg:leading-relaxed">
              {response.answer}
            </div>

            {renderCitations()}
          </div>
        </div>
      </div>
    );
  }

  return null;
}
