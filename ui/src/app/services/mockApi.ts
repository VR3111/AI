// Mock API service to demonstrate UI behavior
// In production, replace with actual API calls with JWT bearer tokens

import {
  AuthState,
  QueryResponse,
  Conversation,
  Document,
  UploadResponse,
  IndexingResponse,
} from '../types/api';

// Mock auth state (in production, verify JWT token)
let currentAuthState: AuthState = 'authenticated';

export const mockApi = {
  // Auth
  getAuthState(): AuthState {
    return currentAuthState;
  },

  setAuthState(state: AuthState) {
    currentAuthState = state;
  },

  // Query endpoint
  async submitQuery(query: string, conversationId?: string): Promise<QueryResponse> {
    await new Promise(resolve => setTimeout(resolve, 800));

    // Mock different response modes based on query content
    if (query.toLowerCase().includes('revenue') || query.toLowerCase().includes('sales')) {
      return {
        mode: 'direct_answer',
        answer: 'Based on the Q4 2024 Financial Report, total revenue was $12.4M, representing a 23% increase year-over-year. Sales were driven primarily by enterprise contracts in North America.',
        citations: [
          { filename: 'Q4-2024-Financial-Report.pdf', page_number: 3 },
          { filename: 'Q4-2024-Financial-Report.pdf', page_number: 7 },
        ],
        query_id: `query_${Date.now()}`,
        timestamp: new Date().toISOString(),
      };
    }

    if (query.toLowerCase().includes('employee') || query.toLowerCase().includes('headcount')) {
      return {
        mode: 'guided_fallback',
        fallback_guidance: 'No exact answer found. Related information exists in: "HR-Policy-2024.pdf" (pages 12-15) regarding organizational structure, and "Annual-Report-2024.pdf" (page 28) regarding workforce metrics. Consider refining your query to target specific aspects.',
        query_id: `query_${Date.now()}`,
        timestamp: new Date().toISOString(),
      };
    }

    if (query.toLowerCase().includes('future') || query.toLowerCase().includes('predict')) {
      return {
        mode: 'hard_refusal',
        refusal_reason: 'Query requests predictive or speculative information. System only answers questions with explicit answers in uploaded documents. No documents contain future projections or predictions.',
        query_id: `query_${Date.now()}`,
        timestamp: new Date().toISOString(),
      };
    }

    // Default: hard refusal for unmatched queries
    return {
      mode: 'hard_refusal',
      refusal_reason: 'No relevant information found in indexed documents. The query cannot be answered from available tenant documents.',
      query_id: `query_${Date.now()}`,
      timestamp: new Date().toISOString(),
    };
  },

  // Conversations
  async listConversations(): Promise<Conversation[]> {
    await new Promise(resolve => setTimeout(resolve, 300));
    return [
      {
        conversation_id: 'conv_001',
        created_at: '2025-12-30T14:23:00Z',
        turns: [
          {
            query: 'What was the total revenue in Q4 2024?',
            response: {
              mode: 'direct_answer',
              answer: 'Based on the Q4 2024 Financial Report, total revenue was $12.4M.',
              citations: [{ filename: 'Q4-2024-Financial-Report.pdf', page_number: 3 }],
              query_id: 'query_001',
              timestamp: '2025-12-30T14:23:15Z',
            },
          },
        ],
      },
      {
        conversation_id: 'conv_002',
        created_at: '2025-12-29T09:15:00Z',
        turns: [
          {
            query: 'What is our hiring plan for next year?',
            response: {
              mode: 'hard_refusal',
              refusal_reason: 'Query requests future planning information. No documents contain explicit hiring plans for future periods.',
              query_id: 'query_002',
              timestamp: '2025-12-29T09:15:10Z',
            },
          },
        ],
      },
      {
        conversation_id: 'conv_003',
        created_at: '2025-12-28T16:42:00Z',
        turns: [
          {
            query: 'How many employees do we have?',
            response: {
              mode: 'guided_fallback',
              fallback_guidance: 'No exact answer found. Related information exists in: "Annual-Report-2024.pdf" (page 28) regarding workforce metrics.',
              query_id: 'query_003',
              timestamp: '2025-12-28T16:42:12Z',
            },
          },
        ],
      },
    ];
  },

  async getConversation(conversationId: string): Promise<Conversation | null> {
    await new Promise(resolve => setTimeout(resolve, 300));
    const conversations = await this.listConversations();
    return conversations.find(c => c.conversation_id === conversationId) || null;
  },

  // Documents
  async listDocuments(): Promise<Document[]> {
    await new Promise(resolve => setTimeout(resolve, 400));
    return [
      {
        document_id: 'doc_001',
        filename: 'Q4-2024-Financial-Report.pdf',
        uploaded_at: '2025-12-15T10:30:00Z',
        indexed: true,
        indexed_at: '2025-12-15T10:31:24Z',
        size_bytes: 2457600,
      },
      {
        document_id: 'doc_002',
        filename: 'HR-Policy-2024.pdf',
        uploaded_at: '2025-12-20T14:20:00Z',
        indexed: true,
        indexed_at: '2025-12-20T14:21:15Z',
        size_bytes: 1048576,
      },
      {
        document_id: 'doc_003',
        filename: 'Product-Roadmap-Draft.pdf',
        uploaded_at: '2025-12-30T08:15:00Z',
        indexed: false,
        size_bytes: 524288,
      },
      {
        document_id: 'doc_004',
        filename: 'Annual-Report-2024.pdf',
        uploaded_at: '2025-12-10T09:00:00Z',
        indexed: true,
        indexed_at: '2025-12-10T09:03:45Z',
        size_bytes: 5242880,
      },
    ];
  },

  async uploadDocument(file: File): Promise<UploadResponse> {
    await new Promise(resolve => setTimeout(resolve, 1000));
    return {
      document_id: `doc_${Date.now()}`,
      filename: file.name,
      uploaded_at: new Date().toISOString(),
    };
  },

  async triggerIndexing(documentId: string): Promise<IndexingResponse> {
    await new Promise(resolve => setTimeout(resolve, 500));
    return {
      document_id: documentId,
      status: 'queued',
      message: 'Document queued for indexing. Check status in document list.',
    };
  },

  async deleteDocument(documentId: string): Promise<void> {
    await new Promise(resolve => setTimeout(resolve, 400));
  },
};
