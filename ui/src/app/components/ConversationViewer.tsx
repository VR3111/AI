import { Conversation, QuerySubmitOptions, WorkspaceScope } from '../types/api';
import { ResponseRenderer } from './ResponseRenderer';
import { useState } from 'react';
import { WorkspaceBanner } from './WorkspaceBanner';

type ActiveScope = {
  label: string;
  mode: WorkspaceScope;
};

interface ConversationViewerProps {
  conversation: Conversation;
  onClose: () => void;
  onSubmitQuery?: (query: string, options?: QuerySubmitOptions) => Promise<void>;
  isProcessing?: boolean;
  activeScope?: ActiveScope | null;
  onClearScope?: () => void;
  onExitDocumentWorkspace?: () => void;
  onNewDocumentWorkspaceChat?: () => void;
  onClearDocumentWorkspaceChat?: () => void;
}

export function ConversationViewer({
  conversation,
  onClose,
  onSubmitQuery,
  isProcessing = false,
  activeScope,
  onClearScope,
  onExitDocumentWorkspace,
  onNewDocumentWorkspaceChat,
  onClearDocumentWorkspaceChat,
}: ConversationViewerProps) {
  const [hoveredQueries, setHoveredQueries] = useState<Set<number>>(new Set());
  const [query, setQuery] = useState('');
  const [isFocused, setIsFocused] = useState(false);

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const toggleHover = (index: number, isHovered: boolean) => {
    setHoveredQueries(prev => {
      const newSet = new Set(prev);
      if (isHovered) {
        newSet.add(index);
      } else {
        newSet.delete(index);
      }
      return newSet;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isProcessing && onSubmitQuery) {
      await onSubmitQuery(query.trim());
      setQuery('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (query.trim() && !isProcessing && onSubmitQuery) {
        handleSubmit(e as any);
      }
    }
  };

  return (
    <div className="h-full min-w-0 flex flex-col bg-background">
      <div className="px-3.5 py-3.5 sm:p-4 lg:p-6 bg-card/50 backdrop-blur-sm border-b border-border/50 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="mb-0.5 text-base lg:mb-1 lg:text-xl">Conversation History</h2>
          <p className="text-[11px] leading-5 text-muted-foreground lg:text-sm">
            {formatDate(conversation.created_at)}
          </p>
        </div>
        <button
          onClick={onClose}
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center self-start rounded-xl bg-secondary/50 hover:bg-secondary text-secondary-foreground transition-all duration-150 lg:duration-200 border border-border/30 hover:border-border/60 relative overflow-hidden group"
          aria-label="Close conversation"
        >
          <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent pointer-events-none" />
          <svg
            className="relative h-4 w-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3.5 py-3.5 sm:p-4 lg:p-8 pb-28 lg:pb-8">
        <div className="max-w-3xl mx-auto w-full space-y-4 lg:space-y-8">
          {activeScope && (
            <WorkspaceBanner
              scope={activeScope}
              onClearScope={onClearScope}
              onExitDocumentWorkspace={onExitDocumentWorkspace}
              onNewDocumentWorkspaceChat={onNewDocumentWorkspaceChat}
              onClearDocumentWorkspaceChat={onClearDocumentWorkspaceChat}
            />
          )}

          {conversation.turns.map((turn, idx) => (
            <div key={idx} className="space-y-2.5 lg:space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-300 lg:duration-500" style={{ animationDelay: `${idx * 30}ms` }}>
              {/* User's Question */}
              <div>
                <div className="mb-1.5 text-[10px] uppercase tracking-[0.16em] text-muted-foreground lg:mb-3 lg:text-xs">
                  Your Question
                </div>
                <div 
                  className="p-2.5 lg:p-5 bg-card/50 backdrop-blur-sm border border-border/50 rounded-xl lg:rounded-xl shadow-sm relative group"
                  onMouseEnter={() => toggleHover(idx, true)}
                  onMouseLeave={() => toggleHover(idx, false)}
                >
                  {/* Glossy highlight */}
                  <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent rounded-lg lg:rounded-xl pointer-events-none" />
                  
                  <div className="flex items-start gap-2.5 lg:gap-3 relative">
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
                    <div className="flex-1 text-[14px] leading-6 text-foreground/90 lg:text-base">{turn.query}</div>
                    
                    {hoveredQueries.has(idx) && (
                      <div className="absolute -right-2 top-0 flex gap-1 animate-in fade-in slide-in-from-right-2 duration-150 lg:duration-200">
                        <button
                          onClick={() => copyToClipboard(turn.query)}
                          className="w-7 h-7 rounded-lg bg-card/80 backdrop-blur-sm border border-border/50 hover:border-primary/50 flex items-center justify-center transition-all duration-150 lg:duration-200 hover:bg-primary/10 relative overflow-hidden"
                          aria-label="Copy query"
                        >
                          <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent pointer-events-none" />
                          <svg className="w-3.5 h-3.5 text-muted-foreground hover:text-primary relative" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
              
              {/* System Response */}
              <div>
                <div className="mb-1.5 text-[10px] uppercase tracking-[0.16em] text-muted-foreground lg:mb-3 lg:text-xs">System Response</div>
                <ResponseRenderer
                  response={turn.response}
                  submittedQuery={turn.query}
                  onSubmitQuery={onSubmitQuery}
                  isProcessing={isProcessing}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Persistent Input Bar */}
      <div className="fixed lg:relative bottom-0 left-0 right-0 px-3.5 pt-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] sm:p-4 lg:p-6 bg-gradient-to-t from-card via-card/95 to-card/80 backdrop-blur-xl border-t border-border/50">
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
              className={`w-full px-4 lg:px-6 py-3 pr-14 lg:py-4 lg:pr-16 bg-input-background border rounded-xl lg:rounded-2xl outline-none transition-all duration-150 lg:duration-300 placeholder:text-muted-foreground/50 shadow-lg text-[15px] lg:text-base ${
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
                  className="w-9 h-9 lg:w-9 lg:h-9 rounded-lg lg:rounded-xl bg-primary/10 hover:bg-primary/20 border border-primary/20 hover:border-primary/30 flex items-center justify-center transition-all duration-150 lg:duration-200 group relative overflow-hidden"
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
                <div className="w-9 h-9 lg:w-9 lg:h-9 rounded-lg lg:rounded-xl bg-secondary/30 border border-border/30 flex items-center justify-center relative overflow-hidden">
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
          <div className="mt-1.5 lg:mt-3 flex items-center justify-between text-[10px] lg:text-xs text-muted-foreground/70 px-1.5 lg:px-2">
            <span>Press Enter to submit</span>
            <span className="hidden sm:inline">Continue this conversation</span>
          </div>
        </form>
      </div>
    </div>
  );
}
