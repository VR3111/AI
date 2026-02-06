import { useState, useEffect } from "react";
import { AuthGuard } from "./components/AuthGuard";
import { QueryInterface } from "./components/QueryInterface";
import { LeftSidebar } from "./components/LeftSidebar";
import { ConversationViewer } from "./components/ConversationViewer";
import { ThemeToggle } from "./components/ThemeToggle";
import { MobileDrawer } from "./components/MobileDrawer";
import { SettingsPanel, SettingsState } from "./components/SettingsPanel";
import { api } from "./services/api";
import { QueryResponse, Document, Conversation } from "./types/api";
import { toast, Toaster } from "sonner";

type View = "query" | "conversation";

function App() {
  const [authState, setAuthState] = useState(api.getAuthState());
  const [currentResponse, setCurrentResponse] = useState<QueryResponse | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [selectedConversationDetail, setSelectedConversationDetail] = useState<Conversation | null>(null);
  const [currentView, setCurrentView] = useState<View>("query");
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [submittedQuery, setSubmittedQuery] = useState<string>("");
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settings, setSettings] = useState<SettingsState>({
    autoIndexDocuments: false,
    showDocumentBadges: true,
    confirmBeforeDelete: true,
    darkMode: true,
    compactView: false,
    enableNotifications: true,
    dataRetention: true,
  });

  useEffect(() => {
    if (authState === "authenticated") {
      loadDocuments();
      loadConversations();
    }
  }, [authState]);

  const loadDocuments = async () => {
    setIsLoadingDocuments(true);
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
    } catch (error) {
      toast.error("Failed to load documents");
    } finally {
      setIsLoadingDocuments(false);
    }
  };

  const loadConversations = async () => {
    setIsLoadingConversations(true);
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      toast.error("Failed to load conversations");
    } finally {
      setIsLoadingConversations(false);
    }
  };

  const handleNewConversation = () => {
    setSelectedConversationId(null);
    setSelectedConversationDetail(null);
    setCurrentView("query");
    setCurrentResponse(null);
    setSubmittedQuery("");
    toast.success("Started new conversation");
  };


  const handleSubmitQuery = async (query: string) => {
    console.log("SUBMIT_QUERY_CALLED", query);
    setIsProcessing(true); // safe to do BEFORE await

    try {
      console.log("APP_BEFORE_AWAIT_SUBMIT_QUERY");
      const response = await api.submitQuery(query);

      setSubmittedQuery(query);
      setCurrentResponse(response);

      const convId = response.conversation_id;

      setSelectedConversationId(convId);
      setCurrentView("conversation");

      const conversationDetail = await api.getConversation(convId);
      setSelectedConversationDetail(conversationDetail);

      await loadConversations();
    } catch (error) {
      console.error("handleSubmitQuery failed", error);
      toast.error("Failed to process query");
    } finally {
      setIsProcessing(false);
    }
  };


  const handleUploadDocument = async (file: File) => {
    try {
      const response = await api.uploadDocument(file);
      toast.success(`Document "${response.filename}" uploaded successfully`);
      await loadDocuments();
    } catch (error) {
      toast.error("Failed to upload document");
    }
  };

  const handleTriggerIndexing = async (documentId: string) => {
    try {
      const response = await api.triggerIndexing(documentId);
      toast.success(response.message || "Indexing triggered");
      setTimeout(() => loadDocuments(), 1000);
    } catch (error) {
      toast.error("Failed to trigger indexing");
    }
  };

  const handleDeleteDocument = async (filename: string) => {
    const doc = documents.find((d) => d.filename === filename);
    if (!doc) return;

    if (settings.confirmBeforeDelete) {
      if (!confirm(`Delete "${doc.filename}"? This action cannot be undone.`)) {
        return;
      }
    }

    try {
      await api.deleteDocument(filename);
      toast.success("Document deleted");
      await loadDocuments();
    } catch (error) {
      toast.error("Failed to delete document");
    }
  };

  const handleSelectConversation = async (conversationId: string) => {
    setSelectedConversationId(conversationId);
    setCurrentView("conversation");

    try {
      const conversationDetail = await api.getConversation(conversationId);
      setSelectedConversationDetail(conversationDetail);
    } catch (error) {
      toast.error("Failed to load conversation details");
      setSelectedConversationDetail(null);
    }
  };

  const handleCloseConversation = () => {
    setSelectedConversationId(null);
    setSelectedConversationDetail(null);
    setCurrentView("query");
  };

  const handleShare = () => {
    toast.success("Share link copied to clipboard");
  };

  const handleUpdateSettings = (updates: Partial<SettingsState>) => {
    setSettings((prev) => ({ ...prev, ...updates }));
  };

  return (
    <AuthGuard authState={authState}>

      {/* 🔎 UI build marker — REMOVE AFTER DEBUG */}
      <div
        style={{
          position: "fixed",
          bottom: 4,
          right: 8,
          fontSize: 10,
          opacity: 0.6,
          zIndex: 9999,
          pointerEvents: "none",
        }}
      >
        UI-BUILD: 2026-01-26-A
      </div>



      <div className="h-screen flex flex-col">
        <Toaster position="top-right" richColors />

        {/* Top Navigation Bar */}
        <div className="bg-gradient-to-r from-card via-card to-card/95 backdrop-blur-xl border-b border-border/50 px-4 lg:px-6 py-3 lg:py-4 flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-3 lg:gap-4">
            {/* Mobile hamburger */}
            <button
              onClick={() => setIsMobileDrawerOpen(true)}
              className="lg:hidden w-9 h-9 flex items-center justify-center rounded-lg hover:bg-secondary/50 transition-all duration-150"
              aria-label="Open menu"
            >
              <svg className="w-5 h-5 text-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>

            <div className="w-8 h-8 lg:w-10 lg:h-10 bg-gradient-to-br from-primary to-primary/80 rounded-lg lg:rounded-xl flex items-center justify-center shadow-lg shadow-primary/20">
              <svg className="w-4 h-4 lg:w-5 lg:h-5 text-primary-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>

            <div>
              <div className="flex items-center gap-2">
                <span className="text-base lg:text-lg">P1</span>
                <span className="hidden lg:inline-flex px-2 py-0.5 bg-primary/10 text-primary text-xs rounded-md border border-primary/20">
                  v1.0
                </span>
              </div>
              <div className="hidden lg:block text-xs text-muted-foreground">Document-faithful response system</div>
            </div>
          </div>

          <div className="flex items-center gap-2 lg:gap-3">
            <div className="hidden lg:flex px-3 py-1.5 bg-secondary/30 rounded-lg border border-border/30">
              <div className="text-xs text-muted-foreground">
                Tenant: <span className="text-foreground/90 ml-1">Auto-detected via JWT</span>
              </div>
            </div>
            <div className="hidden lg:block h-6 w-px bg-border/50" />

            <button
              onClick={handleShare}
              className="w-9 h-9 lg:w-auto flex items-center justify-center lg:justify-start gap-2 lg:px-3 lg:py-1.5 bg-secondary/30 hover:bg-secondary/50 rounded-lg border border-border/30 hover:border-border/50 transition-all duration-150 group"
              aria-label="Share"
            >
              <svg className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
              </svg>
              <span className="hidden lg:inline text-xs text-muted-foreground group-hover:text-foreground transition-colors">Share</span>
            </button>

            <button
              onClick={() => setIsSettingsOpen(true)}
              className="w-9 h-9 lg:w-auto flex items-center justify-center lg:justify-start gap-2 lg:px-3 lg:py-1.5 bg-secondary/30 hover:bg-secondary/50 rounded-lg border border-border/30 hover:border-border/50 transition-all duration-150 group"
              aria-label="Settings"
            >
              <svg className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span className="hidden lg:inline text-xs text-muted-foreground group-hover:text-foreground transition-colors">Settings</span>
            </button>

            <ThemeToggle />
          </div>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Desktop Sidebar - Hidden on mobile */}
          <div className="hidden lg:block">
            <LeftSidebar
              conversations={conversations}
              documents={documents}
              selectedConversationId={selectedConversationId}
              onSelectConversation={handleSelectConversation}
              onNewConversation={handleNewConversation}
              onUploadDocument={handleUploadDocument}
              onIndexDocument={handleTriggerIndexing}
              onDeleteDocument={handleDeleteDocument}
              onOpenSettings={() => setIsSettingsOpen(true)}
              isLoadingDocuments={isLoadingDocuments}
              isLoadingConversations={isLoadingConversations}
              isCollapsed={isSidebarCollapsed}
              onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
              showDocumentBadges={settings.showDocumentBadges}
              confirmBeforeDelete={settings.confirmBeforeDelete}
            />
          </div>

          {/* Mobile Drawer */}
          <MobileDrawer
            isOpen={isMobileDrawerOpen}
            onClose={() => setIsMobileDrawerOpen(false)}
            onOpenSettings={() => setIsSettingsOpen(true)}
            conversations={conversations}
            documents={documents}
            selectedConversationId={selectedConversationId}
            onSelectConversation={handleSelectConversation}
            onNewConversation={handleNewConversation}
            onUploadDocument={handleUploadDocument}
            onIndexDocument={handleTriggerIndexing}
            onDeleteDocument={handleDeleteDocument}
            isLoadingDocuments={isLoadingDocuments}
            isLoadingConversations={isLoadingConversations}
            showDocumentBadges={settings.showDocumentBadges}
            confirmBeforeDelete={settings.confirmBeforeDelete}
          />

          {/* Settings Panel */}
          <SettingsPanel
            isOpen={isSettingsOpen}
            onClose={() => setIsSettingsOpen(false)}
            settings={settings}
            onUpdateSettings={handleUpdateSettings}
          />

          {/* Main Content Area */}
          <div className="flex-1">
            {currentView === "query" ? (
              <QueryInterface
                onSubmitQuery={handleSubmitQuery}
                currentResponse={currentResponse}
                isProcessing={isProcessing}
                submittedQuery={submittedQuery}
              />
            ) : selectedConversationDetail ? (
              <ConversationViewer
                conversation={selectedConversationDetail}
                onClose={handleCloseConversation}
                onSubmitQuery={handleSubmitQuery}
                isProcessing={isProcessing}
              />
            ) : null}
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}

export default App;
