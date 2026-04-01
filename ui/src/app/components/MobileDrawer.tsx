import { useEffect, useRef } from "react";
import { Document, Conversation } from "../types/api";
import { LeftSidebar } from "./LeftSidebar";

interface MobileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenSettings: () => void;
  onOpenSupport: () => void;
  onOpenAuth: () => void;
  onSignOut: () => void;
  conversations: Conversation[];
  documents: Document[];
  selectedConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (conversationId: string) => void;
  onUploadDocument: (file: File) => void;
  onIndexDocument: (documentId: string) => void;
  onDeleteDocument: (documentId: string) => void;
  onOpenDocumentWorkspace: (document: Document) => void;
  onStartNewDocumentWorkspaceChat: (document: Document) => void;
  isLoadingDocuments?: boolean;
  isLoadingConversations?: boolean;
  showDocumentBadges?: boolean;
  confirmBeforeDelete?: boolean;
}

export function MobileDrawer({
  isOpen,
  onClose,
  onOpenSettings,
  onOpenSupport,
  onOpenAuth,
  onSignOut,
  conversations,
  documents,
  selectedConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onUploadDocument,
  onIndexDocument,
  onDeleteDocument,
  onOpenDocumentWorkspace,
  onStartNewDocumentWorkspaceChat,
  isLoadingDocuments = false,
  isLoadingConversations = false,
  showDocumentBadges = true,
  confirmBeforeDelete = true,
}: MobileDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

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
        className="absolute left-0 top-0 h-full w-[88%] max-w-[24rem] overflow-hidden rounded-r-3xl border-r border-border/50 bg-card shadow-[0_24px_80px_-28px_rgba(0,0,0,0.9)]"
        role="dialog"
        aria-modal="true"
        aria-label="Navigation drawer"
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
          onDeleteConversation={onDeleteConversation}
          onUploadDocument={onUploadDocument}
          onIndexDocument={onIndexDocument}
          onDeleteDocument={onDeleteDocument}
          onOpenDocumentWorkspace={(document) => {
            onOpenDocumentWorkspace(document);
            onClose();
          }}
          onStartNewDocumentWorkspaceChat={(document) => {
            onStartNewDocumentWorkspaceChat(document);
            onClose();
          }}
          onOpenSettings={() => {
            onOpenSettings(); // open SettingsPanel
            onClose(); // close drawer
          }}
          onOpenSupport={() => {
            onOpenSupport();
            onClose();
          }}
          onOpenAuth={() => {
            onOpenAuth();
            onClose();
          }}
          onSignOut={() => {
            onSignOut();
            onClose();
          }}
          isLoadingDocuments={isLoadingDocuments}
          isLoadingConversations={isLoadingConversations}
          isCollapsed={false}
          onToggleCollapse={onClose}
          showDocumentBadges={showDocumentBadges}
          confirmBeforeDelete={confirmBeforeDelete}
          mobileMode
        />
      </div>
    </div>
  );
}
