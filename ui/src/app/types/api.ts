// API types for the document Q&A system

export type AuthState = "unauthenticated" | "unauthorized" | "authenticated";
export type IdentityType = "authenticated" | "guest";

export type ResponseMode = "direct_answer" | "guided_fallback" | "hard_refusal";

// Matches backend citation object returned by POST /query
export interface DocumentCitation {
  source: string; // e.g. "data/tenants/acme/docs/volvo.pdf"
  page: number;   // e.g. 18
  score: number;  // distance score
  snippet: string;
}

export interface MatchedDocumentOption {
  source: string;
  display_name: string;
}

export type WorkspaceScope = "global" | "document";

export interface CompareResultItem {
  source: string;
  display_name: string;
  value: string | null;
  found: boolean;
}

export interface ComparePickerCandidate {
  source: string;
  display_name: string;
  confidence: "high" | "medium" | "low";
  matched_alias?: string | null;
  retrieval_score?: number;
}

export interface ComparePickerSide {
  source: string;
  display_name: string;
  confidence: "high" | "medium" | "low";
  matched_alias?: string | null;
}

export interface ComparePickerState {
  left?: ComparePickerSide | null;
  right?: ComparePickerSide | null;
  candidates?: ComparePickerCandidate[];
  can_submit?: boolean;
}

export interface QuerySubmitOptions {
  selectedSource?: string;
  selectedSourceLabel?: string;
  compareSources?: string[];
  compareFocusQuery?: string;
  activateScope?: boolean;
  workspaceScope?: WorkspaceScope;
  followUpContextEnabled?: boolean;
  compareFollowUpEnabled?: boolean;
}

export interface ConversationScopeMeta {
  source: string;
  label: string;
  mode: WorkspaceScope;
}

export interface ConversationCompareMeta {
  sources: string[];
  labels: string[];
  field?: string;
}

// Backend response from POST /query
export interface QueryResponse {
  request_id: string;
  created_at: string;
  tenant_id: string;
  conversation_id: string;
  query: string;
  mode: ResponseMode;
  answer: string;
  citations: DocumentCitation[];
  artifacts: {
    reason?: string;
    additional_resources?: any[];
    best_score?: number;
    compare_field?: string;
    compare_focus_query?: string;
    compare_results?: CompareResultItem[];
    compare_picker?: ComparePickerState;
    matched_documents?: string[];
    matched_document_options?: MatchedDocumentOption[];
    selected_source?: string;
    selected_source_display_name?: string;
    workspace_scope?: WorkspaceScope;
  };
  debug: any | null;
}

export interface ConversationTurn {
  query: string;
  response: QueryResponse;
}

// Backend response from GET /conversations/{id}
export interface ConversationDetail {
  tenant_id: string;
  conversation_id: string;
  items: Array<{
    request_id: string;
    created_at: string;
    query: string;
    mode: ResponseMode;
    answer: string;
    citations_json: string;
    artifacts_json: string;
    debug_json: string | null;
    response_json: string;
  }>;
}

// Backend response from GET /conversations
export interface ConversationListItem {
  conversation_id: string;
  created_at: string;
  last_activity_at: string;
  title?: string;
  selected_source?: string;
  selected_source_display_name?: string;
  workspace_scope?: WorkspaceScope;
}

export interface ConversationsListResponse {
  tenant_id: string;
  conversations: ConversationListItem[];
}

// Derived type for UI consumption
export interface Conversation {
  conversation_id: string;
  created_at: string;
  last_activity_at: string;
  title?: string;
  turns?: ConversationTurn[];
  scope?: ConversationScopeMeta | null;
  compare?: ConversationCompareMeta | null;
}

// Backend response from GET /tenants/{id}/documents
export interface DocumentListItem {
  filename: string;
  source: string;
  size_bytes: number;
  uploaded_at: string;
}

export interface DocumentsListResponse {
  tenant_id: string;
  documents: DocumentListItem[];
}

// UI-friendly document type
export interface Document {
  filename: string;
  source: string;
  uploaded_at: string;
  size_bytes: number;
  indexed: boolean;
}

// Backend response from POST /tenants/{id}/documents
export interface UploadResponse {
  tenant_id: string;
  filename: string;
  stored_path: string;
  indexed: boolean;
  message: string;
}

// Backend response from POST /tenants/{id}/documents/index
export interface IndexingResponse {
  tenant_id: string;
  indexed: boolean;
  message: string;
}

// Backend response from DELETE /tenants/{id}/documents/{filename}
export interface DeleteResponse {
  tenant_id: string;
  deleted: boolean;
  filename: string;
  message: string;
}

export type SupportRequestType = "issue" | "feature" | "contact";

export interface SupportRequestPayload {
  request_type: SupportRequestType;
  subject: string;
  contact_email: string;
  details: string;
  conversation_id?: string | null;
  client_timestamp: string;
}

export interface SupportRequestResponse {
  status: string;
  request_type: SupportRequestType;
  recipient: string;
  tenant_id: string;
  conversation_id: string | null;
  timestamp: string;
}

export interface IdentitySession {
  authenticated: boolean;
  identity_type: IdentityType;
  tenant_id: string;
  user_id: string;
  email: string | null;
  display_name: string | null;
  can_upgrade: boolean;
  pending_guest_tenant_id: string | null;
}

export interface GuestUpgradeResponse {
  status: string;
  guest_tenant_id: string;
  guest_user_id: string;
  target_tenant_id: string;
  target_user_id: string;
}

export interface GuestUpgradeTicketResponse {
  status: string;
  ticket: string;
  guest_tenant_id: string;
}
