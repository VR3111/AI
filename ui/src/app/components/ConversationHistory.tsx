import { Conversation } from '../types/api';

interface ConversationHistoryProps {
  conversations: Conversation[];
  selectedConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
  isLoading?: boolean;
}

export function ConversationHistory({
  conversations,
  selectedConversationId,
  onSelectConversation,
  isLoading = false,
}: ConversationHistoryProps) {
  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) {
      return `${diffMins}m ago`;
    } else if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else if (diffDays < 7) {
      return `${diffDays}d ago`;
    } else {
      return new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
      }).format(date);
    }
  };

  const getResponseModeColor = (mode: string): string => {
    switch (mode) {
      case 'direct_answer':
        return 'text-emerald-400';
      case 'guided_fallback':
        return 'text-amber-400';
      case 'hard_refusal':
        return 'text-zinc-400';
      default:
        return 'text-muted-foreground';
    }
  };

  const getResponseModeIcon = (mode: string) => {
    switch (mode) {
      case 'direct_answer':
        return (
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
        );
      case 'guided_fallback':
        return (
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2.5}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        );
      case 'hard_refusal':
        return (
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
          </svg>
        );
      default:
        return null;
    }
  };

  return (
    <div className="h-full flex flex-col bg-card border-r border-border/50">
      <div className="p-6 border-b border-border/50">
        <h2 className="mb-1">Conversation History</h2>
        <p className="text-xs text-muted-foreground">View and resume past conversations</p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-6 text-center">
            <div className="inline-flex items-center gap-2 text-muted-foreground">
              <div className="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
              <span>Loading...</span>
            </div>
          </div>
        ) : conversations.length === 0 ? (
          <div className="p-6 text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-secondary/50 rounded-xl mb-3">
              <svg className="w-6 h-6 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
            </div>
            <p className="text-sm text-muted-foreground">No past conversations</p>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {conversations.map(conversation => {
              const firstTurn = conversation.turns[0];
              const isSelected = conversation.conversation_id === selectedConversationId;

              return (
                <button
                  key={conversation.conversation_id}
                  onClick={() => onSelectConversation(conversation.conversation_id)}
                  className={`w-full text-left p-4 rounded-xl transition-all duration-200 ${
                    isSelected
                      ? 'bg-primary/10 border border-primary/30 shadow-lg shadow-primary/5'
                      : 'bg-secondary/30 hover:bg-secondary/50 border border-border/30 hover:border-border/60'
                  }`}
                >
                  <div className="flex items-start gap-3 mb-3">
                    <div className={`flex-shrink-0 mt-0.5 ${getResponseModeColor(firstTurn.response.mode)}`}>
                      {getResponseModeIcon(firstTurn.response.mode)}
                    </div>
                    <div className="flex-1 min-w-0 text-sm leading-relaxed line-clamp-2 text-foreground/90">
                      {firstTurn.query}
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                      {conversation.turns.length} turn{conversation.turns.length !== 1 ? 's' : ''}
                    </span>
                    <span className="text-xs text-muted-foreground/70">
                      {formatDate(conversation.created_at)}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}