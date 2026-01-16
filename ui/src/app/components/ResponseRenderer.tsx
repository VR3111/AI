import { QueryResponse } from "../types/api";
import { Tooltip } from "./Tooltip";
import { useMemo, useState } from "react";

interface ResponseRendererProps {
  response: QueryResponse;
}

function getFilenameFromSource(source?: string) {
  if (!source) return "Unknown source";
  const parts = source.split("/");
  return parts[parts.length - 1] || source;
}

export function ResponseRenderer({ response }: ResponseRendererProps) {
  const [hoveredAnswer, setHoveredAnswer] = useState(false);
  const [citationsOpen, setCitationsOpen] = useState(false);

  const hasCitations = !!response.citations && response.citations.length > 0;

  const accent = useMemo(() => {
    if (response.mode === "direct_answer") return "emerald";
    if (response.mode === "guided_fallback") return "amber";
    return "zinc";
  }, [response.mode]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
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

  // -----------------------------
  // DIRECT ANSWER
  // -----------------------------
  if (response.mode === "direct_answer") {
    return (
      <div
        className="relative bg-gradient-to-br from-emerald-500/10 via-emerald-500/5 to-transparent rounded-lg lg:rounded-2xl p-4 lg:p-6 border border-emerald-500/20 shadow-lg backdrop-blur-sm group"
        onMouseEnter={() => setHoveredAnswer(true)}
        onMouseLeave={() => setHoveredAnswer(false)}
      >
        <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent rounded-lg lg:rounded-2xl pointer-events-none" />

        <div className="flex items-start gap-3 lg:gap-4 relative">
          <div className="flex-shrink-0 mt-0.5 lg:mt-1">
            <Tooltip content="Answer found directly in documents">
              <div className="w-7 h-7 lg:w-8 lg:h-8 rounded-lg lg:rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/25">
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
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
            </Tooltip>
          </div>

          <div className="flex-1 min-w-0">
            <div className="mb-2 lg:mb-3">
              <span className="inline-flex items-center gap-1.5 px-2 lg:px-3 py-0.5 lg:py-1 bg-emerald-500/20 text-emerald-400 rounded-lg backdrop-blur-sm border border-emerald-500/30 text-[10px] lg:text-xs">
                <svg
                  className="w-2 h-2 lg:w-3 lg:h-3"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <span className="tracking-wide uppercase">Direct Answer</span>
              </span>
            </div>

            <div className="text-sm lg:text-base text-foreground leading-relaxed mb-3 lg:mb-4 whitespace-pre-wrap relative">
              {response.answer}
              {hoveredAnswer && (
                <div className="hidden lg:flex absolute -right-2 top-0 gap-1 animate-in fade-in slide-in-from-right-2 duration-150">
                  <button
                    onClick={() => copyToClipboard(response.answer)}
                    className="w-7 h-7 rounded-lg bg-card/80 backdrop-blur-sm border border-border/50 hover:border-emerald-500/50 flex items-center justify-center transition-all duration-150 hover:bg-emerald-500/10"
                    aria-label="Copy answer"
                  >
                    <svg
                      className="w-3.5 h-3.5 text-muted-foreground hover:text-emerald-400"
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
        className="relative bg-gradient-to-br from-amber-500/10 via-amber-500/5 to-transparent rounded-lg lg:rounded-2xl p-4 lg:p-6 border border-amber-500/20 shadow-lg backdrop-blur-sm group"
        onMouseEnter={() => setHoveredAnswer(true)}
        onMouseLeave={() => setHoveredAnswer(false)}
      >
        <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent rounded-lg lg:rounded-2xl pointer-events-none" />

        <div className="flex items-start gap-3 lg:gap-4 relative">
          <div className="flex-shrink-0 mt-0.5 lg:mt-1">
            <Tooltip content="Guidance provided when answer not found verbatim">
              <div className="w-7 h-7 lg:w-8 lg:h-8 rounded-lg lg:rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/25">
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
            <div className="mb-2 lg:mb-3">
              <span className="inline-flex items-center gap-1.5 px-2 lg:px-3 py-0.5 lg:py-1 bg-amber-500/20 text-amber-400 rounded-lg backdrop-blur-sm border border-amber-500/30 text-[10px] lg:text-xs">
                <svg
                  className="w-2 h-2 lg:w-3 lg:h-3"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <span className="tracking-wide uppercase">Guided Fallback</span>
              </span>
            </div>

            <div className="text-sm lg:text-base text-foreground leading-relaxed whitespace-pre-wrap relative">
              {response.answer}
              {hoveredAnswer && (
                <div className="hidden lg:flex absolute -right-2 top-0 gap-1 animate-in fade-in slide-in-from-right-2 duration-150">
                  <button
                    onClick={() => copyToClipboard(response.answer)}
                    className="w-7 h-7 rounded-lg bg-card/80 backdrop-blur-sm border border-border/50 hover:border-amber-500/50 flex items-center justify-center transition-all duration-150 hover:bg-amber-500/10"
                    aria-label="Copy guidance"
                  >
                    <svg
                      className="w-3.5 h-3.5 text-muted-foreground hover:text-amber-400"
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
              )}
            </div>

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
        className="relative bg-gradient-to-br from-zinc-500/10 via-zinc-500/5 to-transparent rounded-lg lg:rounded-2xl p-4 lg:p-6 border border-zinc-500/20 shadow-lg backdrop-blur-sm group"
        onMouseEnter={() => setHoveredAnswer(true)}
        onMouseLeave={() => setHoveredAnswer(false)}
      >
        <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent rounded-lg lg:rounded-2xl pointer-events-none" />

        <div className="flex items-start gap-3 lg:gap-4 relative">
          <div className="flex-shrink-0 mt-0.5 lg:mt-1">
            <Tooltip content="Query cannot be answered from documents">
              <div className="w-7 h-7 lg:w-8 lg:h-8 rounded-lg lg:rounded-xl bg-gradient-to-br from-zinc-600 to-zinc-700 flex items-center justify-center shadow-lg shadow-zinc-500/25">
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
            <div className="mb-2 lg:mb-3">
              <span className="inline-flex items-center gap-1.5 px-2 lg:px-3 py-0.5 lg:py-1 bg-zinc-500/20 text-zinc-400 rounded-lg backdrop-blur-sm border border-zinc-500/30 text-[10px] lg:text-xs">
                <svg
                  className="w-2 h-2 lg:w-3 lg:h-3"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <span className="tracking-wide uppercase">Hard Refusal</span>
              </span>
            </div>

            <div className="text-sm lg:text-base text-foreground leading-relaxed whitespace-pre-wrap relative">
              {response.answer}
              {hoveredAnswer && (
                <div className="hidden lg:flex absolute -right-2 top-0 gap-1 animate-in fade-in slide-in-from-right-2 duration-150">
                  <button
                    onClick={() => copyToClipboard(response.answer)}
                    className="w-7 h-7 rounded-lg bg-card/80 backdrop-blur-sm border border-border/50 hover:border-zinc-500/50 flex items-center justify-center transition-all duration-150 hover:bg-zinc-500/10"
                    aria-label="Copy reason"
                  >
                    <svg
                      className="w-3.5 h-3.5 text-muted-foreground hover:text-zinc-300"
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
              )}
            </div>

            {renderCitations()}
          </div>
        </div>
      </div>
    );
  }

  return null;
}
