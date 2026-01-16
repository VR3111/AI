import { useState } from 'react';
import { QueryResponse } from '../types/api';
import { ResponseRenderer } from './ResponseRenderer';

interface QueryInterfaceProps {
  onSubmitQuery: (query: string) => Promise<void>;
  currentResponse: QueryResponse | null;
  isProcessing: boolean;
  submittedQuery?: string;
}

export function QueryInterface({
  onSubmitQuery,
  currentResponse,
  isProcessing,
  submittedQuery,
}: QueryInterfaceProps) {
  const [query, setQuery] = useState('');
  const [isFocused, setIsFocused] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isProcessing) {
      await onSubmitQuery(query.trim());
      setQuery('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (query.trim() && !isProcessing) {
        handleSubmit(e as any);
      }
    }
  };

  return (
    <div className="h-full flex flex-col bg-background">
      <div className="p-4 lg:p-6 bg-card/50 backdrop-blur-sm border-b border-border/50">
        <h1 className="mb-1 lg:mb-2 text-lg lg:text-xl">Document Q&A System</h1>
        <p className="text-xs lg:text-sm text-muted-foreground">
          Ask questions answerable from indexed documents only
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 lg:p-8 pb-32 lg:pb-8">
        {currentResponse && submittedQuery ? (
          <div className="max-w-3xl mx-auto space-y-4 lg:space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300 lg:duration-500">
            {/* User's Question */}
            <div>
              <div className="text-xs text-muted-foreground mb-2 lg:mb-3 uppercase tracking-wider">Your Question</div>
              <div className="p-3 lg:p-5 bg-card/50 backdrop-blur-sm border border-border/50 rounded-lg lg:rounded-xl shadow-sm relative">
                <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent rounded-lg lg:rounded-xl pointer-events-none" />
                <div className="flex items-start gap-2 lg:gap-3 relative">
                  <svg
                    className="w-4 h-4 lg:w-5 lg:h-5 text-primary flex-shrink-0 mt-0.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                    />
                  </svg>
                  <div className="flex-1 text-sm lg:text-base text-foreground/90 leading-relaxed">
                    {submittedQuery}
                  </div>
                </div>
              </div>
            </div>
            
            {/* System Response */}
            <div>
              <div className="text-xs text-muted-foreground mb-2 lg:mb-3 uppercase tracking-wider">System Response</div>
              <ResponseRenderer response={currentResponse} />
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto text-center py-12 lg:py-20">
            <div className="inline-flex items-center justify-center w-16 h-16 lg:w-20 lg:h-20 bg-gradient-to-br from-primary/20 to-primary/5 rounded-xl lg:rounded-2xl mb-4 lg:mb-6 shadow-lg relative">
              <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent rounded-xl lg:rounded-2xl pointer-events-none" />
              <svg
                className="w-8 h-8 lg:w-10 lg:h-10 text-primary/60 relative"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                />
              </svg>
            </div>
            <h3 className="text-sm lg:text-base text-muted-foreground mb-2 lg:mb-3">Ready for your question</h3>
            <p className="text-xs lg:text-sm text-muted-foreground/70 max-w-md mx-auto">
              Ask a question to receive a deterministic response
            </p>
          </div>
        )}
      </div>

      <div className="fixed lg:relative bottom-0 left-0 right-0 p-4 lg:p-6 bg-gradient-to-t from-card via-card/95 to-card/80 backdrop-blur-xl border-t border-border/50">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
          <div className="relative">
            {/* Glossy surface effect */}
            <div className={`absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent rounded-xl lg:rounded-2xl pointer-events-none transition-opacity duration-150 lg:duration-200 ${isFocused ? 'opacity-100' : 'opacity-0'}`} />
            
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder="Type here…"
              className={`w-full px-4 lg:px-6 py-3 lg:py-4 pr-14 lg:pr-16 bg-input-background border rounded-xl lg:rounded-2xl outline-none transition-all duration-150 lg:duration-300 placeholder:text-muted-foreground/50 shadow-lg ${
                isFocused 
                  ? 'ring-2 ring-primary/50 border-primary/50 shadow-2xl shadow-primary/10' 
                  : 'border-input hover:border-input/80'
              }`}
              disabled={isProcessing}
            />
            <div className="absolute right-2 lg:right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
              {isProcessing ? (
                <div className="flex items-center gap-2 px-2 lg:px-3 py-2">
                  <div className="w-3 h-3 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                </div>
              ) : query.trim() ? (
                <button
                  type="submit"
                  className="w-8 h-8 lg:w-9 lg:h-9 rounded-lg lg:rounded-xl bg-primary/10 hover:bg-primary/20 border border-primary/20 hover:border-primary/30 flex items-center justify-center transition-all duration-150 lg:duration-200 group relative overflow-hidden"
                  aria-label="Send message"
                >
                  {/* Glossy highlight */}
                  <div className="absolute inset-0 bg-gradient-to-b from-white/[0.05] to-transparent pointer-events-none" />
                  <svg
                    className="w-3.5 h-3.5 lg:w-4 lg:h-4 text-primary transition-transform duration-150 lg:duration-200 group-hover:translate-x-0.5 relative"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                </button>
              ) : (
                <div className="w-8 h-8 lg:w-9 lg:h-9 rounded-lg lg:rounded-xl bg-secondary/30 border border-border/30 flex items-center justify-center relative overflow-hidden">
                  {/* Glossy highlight */}
                  <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent pointer-events-none" />
                  <svg
                    className="w-3.5 h-3.5 lg:w-4 lg:h-4 text-muted-foreground/30 relative"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                </div>
              )}
            </div>
          </div>
          <div className="mt-2 lg:mt-3 flex items-center justify-between text-[10px] lg:text-xs text-muted-foreground/70 px-2">
            <span>Press Enter to submit</span>
            <span className="hidden sm:inline">Direct answer · Guided fallback · Hard refusal</span>
          </div>
        </form>
      </div>
    </div>
  );
}