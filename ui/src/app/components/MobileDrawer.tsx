import { useState, useEffect, useRef } from "react";
import { Document, Conversation } from "../types/api";
import { UserProfilePopup } from "./UserProfilePopup";
import { LeftSidebar } from "./LeftSidebar";

interface MobileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  conversations: Conversation[];
  documents: Document[];
  selectedConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
  onNewConversation: () => void;
  onUploadDocument: (file: File) => void;
  onIndexDocument: (documentId: string) => void;
  onDeleteDocument: (documentId: string) => void;
  isLoadingDocuments?: boolean;
  isLoadingConversations?: boolean;
  showDocumentBadges?: boolean;
  confirmBeforeDelete?: boolean;
}

export function MobileDrawer({
  isOpen,
  onClose,
  conversations,
  documents,
  selectedConversationId,
  onSelectConversation,
  onNewConversation,
  onUploadDocument,
  onIndexDocument,
  onDeleteDocument,
  isLoadingDocuments = false,
  isLoadingConversations = false,
  showDocumentBadges = true,
  confirmBeforeDelete = true,
}: MobileDrawerProps) {
  const [documentsExpanded, setDocumentsExpanded] = useState(true);
  const [conversationsExpanded, setConversationsExpanded] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  const MAX_ITEMS_PREVIEW = 5;

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        drawerRef.current &&
        !drawerRef.current.contains(event.target as Node)
      ) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.body.style.overflow = "unset";
    };
  }, [isOpen, onClose]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setIsUploading(true);
      await onUploadDocument(file);
      setIsUploading(false);
      e.target.value = "";
    }
  };

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

  // ✅ FIX: guard against undefined turns
  const filteredConversations = conversations.filter((conv) =>
    (conv.turns ?? []).some((turn) =>
      turn.query.toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  const displayedDocuments = documents.slice(0, MAX_ITEMS_PREVIEW);
  const displayedConversations = filteredConversations.slice(
    0,
    MAX_ITEMS_PREVIEW
  );

  const handleConversationSelect = (conversationId: string) => {
    onSelectConversation(conversationId);
    onClose();
  };

  const handleNewConversationClick = () => {
    onNewConversation();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        className="absolute left-0 top-0 h-full w-[81%] max-w-sm bg-background"
      >
        <LeftSidebar
          conversations={conversations}
          documents={documents}
          selectedConversationId={selectedConversationId}
          onSelectConversation={(id) => {
            onSelectConversation(id);
            onClose();
          }}
          onNewConversation={() => {
            onNewConversation();
            onClose();
          }}
          onUploadDocument={onUploadDocument}
          onIndexDocument={onIndexDocument}
          onDeleteDocument={onDeleteDocument}
          onOpenSettings={onClose}
          isLoadingDocuments={isLoadingDocuments}
          isLoadingConversations={isLoadingConversations}
          isCollapsed={false}
          onToggleCollapse={onClose} 
          showDocumentBadges={showDocumentBadges}
          confirmBeforeDelete={confirmBeforeDelete}
        />
      </div>
    </div>
  );
}
