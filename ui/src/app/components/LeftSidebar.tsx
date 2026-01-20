import { useState } from "react";
import { Document, Conversation } from "../types/api";
import { UserProfilePopup } from "./UserProfilePopup";
import { api } from "../services/api";
import { getUserIdentityFromJwt } from "../../../lib/authIdentity";

interface LeftSidebarProps {
  conversations: Conversation[];
  documents: Document[];
  selectedConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
  onNewConversation: () => void;
  onUploadDocument: (file: File) => void;
  onIndexDocument: (documentId: string) => void;
  onDeleteDocument: (documentId: string) => void;
  onOpenSettings: () => void;
  isLoadingDocuments?: boolean;
  isLoadingConversations?: boolean;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  showDocumentBadges?: boolean;
  confirmBeforeDelete?: boolean;
}

export function LeftSidebar({
  conversations,
  documents,
  selectedConversationId,
  onSelectConversation,
  onNewConversation,
  onUploadDocument,
  onIndexDocument,
  onDeleteDocument,
  onOpenSettings,
  isLoadingDocuments = false,
  isLoadingConversations = false,
  isCollapsed = false,
  onToggleCollapse,
  showDocumentBadges = true,
  confirmBeforeDelete = true,
}: LeftSidebarProps) {
  const [documentsExpanded, setDocumentsExpanded] = useState(true);
  const [conversationsExpanded, setConversationsExpanded] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [showAllDocuments, setShowAllDocuments] = useState(false);
  const [showAllConversations, setShowAllConversations] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  const MAX_ITEMS_PREVIEW = 5;

  // User identity (frontend-only, derived from JWT used by API client)
  const { name: userName, email: userEmail } = getUserIdentityFromJwt(
    api.getAuthHeader()
  );

  // --------------------------------------------
  // Upload handler (unchanged behavior)
  // --------------------------------------------
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setIsUploading(true);
      await onUploadDocument(file);
      setIsUploading(false);
      e.target.value = "";
    }
  };

  // --------------------------------------------
  // Helpers: formatting + small UI utilities
  // --------------------------------------------
  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
    }).format(date);
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  // --------------------------------------------
  // Response mode helpers (only used when turns exist)
  // --------------------------------------------
  const getResponseModeColor = (mode: string): string => {
    switch (mode) {
      case "direct_answer":
        return "text-emerald-400";
      case "guided_fallback":
        return "text-amber-400";
      case "hard_refusal":
        return "text-zinc-400";
      default:
        return "text-muted-foreground";
    }
  };

  const getResponseModeIcon = (mode: string) => {
    switch (mode) {
      case "direct_answer":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2.5}
            d="M5 13l4 4L19 7"
          />
        );
      case "guided_fallback":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2.5}
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        );
      case "hard_refusal":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2.5}
            d="M6 18L18 6M6 6l12 12"
          />
        );
      default:
        return null;
    }
  };

  const getConversationSearchText = (conv: Conversation): string => {
    if (conv.title && conv.title.trim()) return conv.title;
    const firstTurnQuery = conv.turns?.[0]?.query;
    if (firstTurnQuery && firstTurnQuery.trim()) return firstTurnQuery;
    return conv.conversation_id;
  };

  const filteredConversations = conversations.filter((conv) => {
    const haystack = getConversationSearchText(conv).toLowerCase();
    const needle = searchQuery.toLowerCase().trim();

    if (!needle) return true;
    return haystack.includes(needle);
  });

  const displayedDocuments = showAllDocuments
    ? documents
    : documents.slice(0, MAX_ITEMS_PREVIEW);

  const displayedConversations = showAllConversations
    ? filteredConversations
    : filteredConversations.slice(0, MAX_ITEMS_PREVIEW);

  // --------------------------------------------
  // Collapsed sidebar UI
  // --------------------------------------------
  if (isCollapsed) {
    return (
      <div className="h-full w-16 flex flex-col items-center bg-card border-r border-border/50 py-4">
        <button
          onClick={onToggleCollapse}
          className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-secondary/50 transition-all duration-200 group mb-4"
          aria-label="Expand sidebar"
        >
          <svg
            className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M13 5l7 7-7 7M5 5l7 7-7 7"
            />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div className="h-full w-80 flex flex-col bg-card border-r border-border/50">
      {/* Collapse Toggle */}
      <div className="px-4 pt-4 pb-2 flex items-center justify-between">
        <div className="text-xs uppercase tracking-wider text-muted-foreground/70">
          Navigation
        </div>
        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-secondary/50 transition-all duration-200 group"
            aria-label="Collapse sidebar"
          >
            <svg
              className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-all duration-200 group-hover:-translate-x-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M11 19l-7-7 7-7m8 14l-7-7 7-7"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Primary Actions */}
      <div className="px-4 pb-4 space-y-2 border-b border-border/30">
        <button
          onClick={onNewConversation}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-primary to-primary/90 text-primary-foreground rounded-xl hover:shadow-lg hover:shadow-primary/25 transition-all duration-200 active:scale-[0.98] group"
        >
          <svg
            className="w-4 h-4 transition-transform duration-200 group-hover:rotate-90"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
          <span>New Conversation</span>
        </button>

        <button
          onClick={() => setIsSearching(!isSearching)}
          className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl transition-all duration-200 ${
            isSearching
              ? "bg-primary/10 text-primary border border-primary/30"
              : "bg-secondary/50 text-secondary-foreground border border-border/30 hover:bg-secondary/70 hover:border-border/50"
          }`}
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <span>Search Conversations</span>
        </button>

        {isSearching && (
          <div className="animate-in slide-in-from-top-2 duration-200">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Type to search..."
              className="w-full px-3 py-2 bg-input-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all duration-200 placeholder:text-muted-foreground/50"
              autoFocus
            />
          </div>
        )}
      </div>

      {/* Upload Document */}
      <div className="px-4 pt-4 pb-3">
        <label className="block group cursor-pointer">
          <input
            type="file"
            className="hidden"
            onChange={handleFileChange}
            accept=".pdf,.doc,.docx,.txt"
            disabled={isUploading}
          />
          <div className="flex items-center justify-center gap-2 px-4 py-2.5 bg-secondary/50 hover:bg-secondary/70 text-foreground/90 rounded-lg border border-border/30 hover:border-border/50 transition-all duration-200 active:scale-[0.98]">
            <svg
              className="w-4 h-4 transition-transform duration-200 group-hover:-translate-y-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
            <span className="text-sm">
              {isUploading ? "Uploading..." : "Upload Document"}
            </span>
          </div>
        </label>
      </div>

      {/* Scrollable Content Area */}
      <div className="flex-1 overflow-y-auto min-h-0 pb-4">
        {/* Documents Section */}
        <div className="border-b border-border/30">
          <button
            onClick={() => setDocumentsExpanded(!documentsExpanded)}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-secondary/30 transition-all duration-200 group"
          >
            <div className="flex items-center gap-2">
              <svg
                className={`w-4 h-4 text-muted-foreground transition-all duration-200 ${
                  documentsExpanded ? "rotate-90" : ""
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
              <span className="text-sm uppercase tracking-wider text-muted-foreground group-hover:text-foreground transition-colors">
                Documents
              </span>
            </div>
            <span className="text-xs bg-secondary/50 px-2 py-0.5 rounded text-muted-foreground">
              {documents.length}
            </span>
          </button>

          {documentsExpanded && (
            <div className="pb-2 animate-in slide-in-from-top-2 duration-300">
              {isLoadingDocuments ? (
                <div className="px-4 py-6 text-center">
                  <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                    <div className="w-3 h-3 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                    <span>Loading...</span>
                  </div>
                </div>
              ) : documents.length === 0 ? (
                <div className="px-4 py-6 text-center">
                  <p className="text-xs text-muted-foreground">
                    No documents yet
                  </p>
                </div>
              ) : (
                <>
                  <div className="px-2 space-y-1">
                    {displayedDocuments.map((doc) => (
                      <div
                        key={doc.filename}
                        className="group bg-secondary/20 hover:bg-secondary/40 rounded-lg p-3 border border-border/20 hover:border-border/40 transition-all duration-200"
                      >
                        <div className="flex items-start gap-2 mb-2">
                          <svg
                            className="w-4 h-4 text-primary flex-shrink-0 mt-0.5"
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

                          <div className="flex-1 min-w-0">
                            <div className="text-sm truncate text-foreground/90 mb-1">
                              {doc.filename}
                            </div>

                            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-2">
                              <span>{formatBytes(doc.size_bytes)}</span>
                            </div>

                            <div
                              className={`transition-all duration-200 ${
                                showDocumentBadges
                                  ? "opacity-100 max-h-8"
                                  : "opacity-0 max-h-0 overflow-hidden"
                              }`}
                            >
                              {doc.indexed ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded text-[10px] border border-emerald-500/30 transition-all duration-200">
                                  <svg
                                    className="w-2 h-2"
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
                                  Indexed
                                </span>
                              ) : (
                                <button
                                  onClick={() => onIndexDocument(doc.filename)}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary/10 text-primary rounded text-[10px] border border-primary/20 hover:bg-primary/20 transition-all duration-200"
                                >
                                  <svg
                                    className="w-2 h-2"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                                    />
                                  </svg>
                                  Index
                                </button>
                              )}
                            </div>
                          </div>
                        </div>

                        <button
                          onClick={() => {
                            if (confirmBeforeDelete) {
                              const confirmed = confirm(
                                `Delete "${doc.filename}"? This action cannot be undone.`
                              );
                              if (confirmed) {
                                onDeleteDocument(doc.filename);
                              }
                            } else {
                              onDeleteDocument(doc.filename);
                            }
                          }}
                          className="w-full text-xs text-destructive/80 hover:text-destructive py-1.5 opacity-0 group-hover:opacity-100 transition-all duration-200 relative flex items-center justify-center gap-1"
                        >
                          <svg
                            className={`w-3 h-3 transition-all duration-200 ${
                              confirmBeforeDelete
                                ? "opacity-100 w-3"
                                : "opacity-0 w-0 overflow-hidden"
                            }`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                            />
                          </svg>
                          <span>Delete</span>
                        </button>
                      </div>
                    ))}
                  </div>

                  {documents.length > MAX_ITEMS_PREVIEW && (
                    <div className="px-2 mt-2">
                      <button
                        onClick={() => setShowAllDocuments(!showAllDocuments)}
                        className="w-full text-xs text-primary hover:text-primary/80 py-2 px-3 rounded-lg hover:bg-primary/5 transition-all duration-200 flex items-center justify-center gap-1.5"
                      >
                        <span>
                          {showAllDocuments
                            ? "Show less"
                            : `View all ${documents.length} documents`}
                        </span>
                        <svg
                          className={`w-3 h-3 transition-transform duration-200 ${
                            showAllDocuments ? "rotate-180" : ""
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
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        {/* Conversation History Section */}
        <div>
          <button
            onClick={() => setConversationsExpanded(!conversationsExpanded)}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-secondary/30 transition-all duration-200 group"
          >
            <div className="flex items-center gap-2">
              <svg
                className={`w-4 h-4 text-muted-foreground transition-all duration-200 ${
                  conversationsExpanded ? "rotate-90" : ""
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
              <span className="text-sm uppercase tracking-wider text-muted-foreground group-hover:text-foreground transition-colors">
                Conversations
              </span>
            </div>

            {/* Shows count from backend list (not dependent on turns) */}
            <span className="text-xs bg-secondary/50 px-2 py-0.5 rounded text-muted-foreground">
              {filteredConversations.length}
            </span>
          </button>

          {conversationsExpanded && (
            <div className="pb-2 animate-in slide-in-from-top-2 duration-300">
              {isLoadingConversations ? (
                <div className="px-4 py-6 text-center">
                  <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                    <div className="w-3 h-3 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                    <span>Loading...</span>
                  </div>
                </div>
              ) : filteredConversations.length === 0 ? (
                <div className="px-4 py-6 text-center">
                  <p className="text-xs text-muted-foreground">
                    {searchQuery
                      ? "No matching conversations"
                      : "No conversations yet"}
                  </p>
                </div>
              ) : (
                <>
                  <div className="px-2 space-y-1">
                    {displayedConversations.map((conversation) => {
                      const isSelected =
                        conversation.conversation_id === selectedConversationId;

                      // ⭐ Safe access: turns may be undefined for list results
                      const firstTurn = conversation.turns?.[0];

                      // Display label:
                      // - show first question if available
                      // - else show conversation id (shortened)
                      // const cachedTitle =
                      //   getConversationTitle(conversation.conversation_id) ||
                      //   "";

                      // const previewText =
                      //   firstTurn?.query?.trim() ||
                      //   cachedTitle ||
                      //   "New conversation";

                      const previewText =
                        conversation.title?.trim() ||
                        firstTurn?.query?.trim() ||
                        "New conversation";

                      return (
                        <button
                          key={conversation.conversation_id}
                          onClick={() =>
                            onSelectConversation(conversation.conversation_id)
                          }
                          className={`w-full text-left p-3 rounded-lg transition-all duration-200 ${
                            isSelected
                              ? "bg-primary/10 border border-primary/30 shadow-lg shadow-primary/5"
                              : "bg-secondary/20 hover:bg-secondary/40 border border-border/20 hover:border-border/40"
                          }`}
                        >
                          <div className="flex items-start gap-2 mb-2">
                            {/* If we have a real first turn, show mode icon.
                                Else show a neutral icon */}
                            <div
                              className={`flex-shrink-0 mt-0.5 ${
                                firstTurn?.response?.mode
                                  ? getResponseModeColor(
                                      firstTurn.response.mode
                                    )
                                  : "text-muted-foreground"
                              }`}
                            >
                              <svg
                                className="w-3 h-3"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                {firstTurn?.response?.mode ? (
                                  getResponseModeIcon(firstTurn.response.mode)
                                ) : (
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                                  />
                                )}
                              </svg>
                            </div>

                            <div className="flex-1 min-w-0 text-sm leading-relaxed line-clamp-2 text-foreground/90">
                              {previewText}
                            </div>
                          </div>

                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground/70">
                              {/* If turns exist, show turns count. Else show "Saved" */}
                              {conversation.turns?.length
                                ? `${conversation.turns.length} turn${
                                    conversation.turns.length !== 1 ? "s" : ""
                                  }`
                                : "Saved"}
                            </span>

                            <span className="text-muted-foreground/50">
                              {formatDate(conversation.created_at)}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  {filteredConversations.length > MAX_ITEMS_PREVIEW && (
                    <div className="px-2 mt-2">
                      <button
                        onClick={() =>
                          setShowAllConversations(!showAllConversations)
                        }
                        className="w-full text-xs text-primary hover:text-primary/80 py-2 px-3 rounded-lg hover:bg-primary/5 transition-all duration-200 flex items-center justify-center gap-1.5"
                      >
                        <span>
                          {showAllConversations
                            ? "Show less"
                            : `View all ${filteredConversations.length} conversations`}
                        </span>
                        <svg
                          className={`w-3 h-3 transition-transform duration-200 ${
                            showAllConversations ? "rotate-180" : ""
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
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Scroll/Profile Divider */}
      <div className="h-[6px] bg-card border-t border-border/30" />

      {/* User Profile Section (desktop behavior unchanged) */}
      <div className="relative border-t border-border/30 p-3">
        <button
          onClick={() => setIsProfileOpen(!isProfileOpen)}
          data-profile-button
          className="w-full flex items-center gap-3 p-2.5 rounded-lg hover:bg-secondary/50 transition-all duration-200 group relative overflow-hidden"
        >
          <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />

          <div className="w-9 h-9 bg-gradient-to-br from-primary to-primary/80 rounded-full flex items-center justify-center text-primary-foreground shadow-lg shadow-primary/20 transition-transform duration-200 group-hover:scale-105 relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-b from-white/10 to-transparent pointer-events-none" />
            <span className="text-sm relative">
              {userName
                .split(" ")
                .map((w) => w[0])
                .slice(0, 2)
                .join("")
                .toUpperCase()}
            </span>
          </div>

          <div className="flex-1 text-left min-w-0 relative">
            <div className="text-sm truncate text-foreground/90">
              {userName}
            </div>
            <div className="text-xs text-muted-foreground truncate">
              {userEmail}
            </div>
          </div>

          <svg
            className={`w-4 h-4 text-muted-foreground transition-transform duration-200 relative ${
              isProfileOpen ? "rotate-180" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 15l7-7 7 7"
            />
          </svg>
        </button>

        <UserProfilePopup
          isOpen={isProfileOpen}
          onClose={() => setIsProfileOpen(false)}
          userName={userName}
          userEmail={userEmail}
          onOpenSettings={onOpenSettings}
          onSignOut={() => {
            setIsProfileOpen(false);
            // Handle sign out
          }}
        />
      </div>
    </div>
  );
}
