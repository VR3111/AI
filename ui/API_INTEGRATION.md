# P1 Frontend - Backend API Integration

This document describes how the P1 frontend is wired to the FastAPI backend.

## Overview

The frontend has been fully wired to communicate with the P1 FastAPI backend. All mock data has been replaced with real API calls.

## Configuration

### Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```bash
VITE_API_BASE_URL=http://localhost:8000
```

- `VITE_API_BASE_URL`: The base URL of your FastAPI backend server
  - Default: `http://localhost:8000`
  - Update this if your backend runs on a different host/port

### Tenant ID

The frontend uses a hardcoded tenant ID (`default-tenant`) since authentication is not enforced at runtime per the project requirements. This is configured in `/src/app/services/api.ts`.

## API Endpoints Used

### Query API
- **POST /query** - Submit a query and get a response
  - Request: `{ query, conversation_id, tenant_id, debug }`
  - Response: QueryResponse with mode, answer, citations, artifacts

### Conversation Management
- **GET /conversations** - List all conversations for the tenant
  - Response: List of conversations with basic metadata
  
- **GET /conversations/{conversation_id}** - Get full conversation details
  - Response: Complete conversation with all query/response turns

### Document Management
- **GET /tenants/{tenant_id}/documents** - List all documents
  - Response: List of documents with filename, size, upload date
  
- **POST /tenants/{tenant_id}/documents** - Upload a document
  - Request: multipart/form-data with PDF file
  - Response: Upload confirmation with auto-indexing status
  
- **DELETE /tenants/{tenant_id}/documents/{filename}** - Delete a document
  - Response: Deletion confirmation
  
- **POST /tenants/{tenant_id}/documents/index** - Re-index all documents
  - Response: Indexing status

## Key Implementation Details

### API Client (`/src/app/services/api.ts`)

The real API client replaces the mock API:

```typescript
import { api } from './services/api';  // Real API
```

Key features:
- Automatic conversation ID generation and management
- Error handling with console logging
- JSON parsing of backend response fields (citations_json, artifacts_json, etc.)
- Proper transformation of backend responses to UI-friendly formats

### Type System (`/src/app/types/api.ts`)

Types have been updated to match the exact backend response shapes:

- `QueryResponse` - Matches POST /query response
- `ConversationDetail` - Matches GET /conversations/{id} response  
- `DocumentsListResponse` - Matches GET /tenants/{id}/documents response
- etc.

### Document Identification

The backend uses **filename** as the document identifier, not a separate `document_id`. All components have been updated accordingly:

- `Document.filename` is the primary identifier
- Delete and index operations use filename
- Backend auto-indexes documents on upload

### Conversation Loading

Conversations are loaded in two steps:

1. **List view** (`GET /conversations`) - Shows conversation summaries
2. **Detail view** (`GET /conversations/{id}`) - Loaded when conversation is selected, includes full history with all turns

### Response Modes

The backend returns one of three modes for each query:

- `direct_answer` - Answer found in documents (has `answer` and `citations`)
- `guided_fallback` - Related content exists but no direct answer (check `artifacts.reason`)
- `hard_refusal` - No relevant information found (check `artifacts.reason`)

All response modes are handled by the existing ResponseRenderer component.

## Authentication

**Important**: Per project requirements:
- Backend auth exists but is **NOT enforced** at runtime
- Frontend does NOT send `Authorization` headers
- Frontend does NOT block UI rendering based on auth state
- This is intentional for development and verification purposes

In production:
1. Add JWT token management
2. Include `Authorization: Bearer <token>` header in all API calls
3. Extract tenant_id from JWT claims
4. Update auth handling in `AuthGuard` component

## Testing the Integration

### Prerequisites
1. Backend server running at configured `VITE_API_BASE_URL`
2. Backend has accessible data directory for tenant documents
3. No authentication required (as per current configuration)

### Verification Steps

1. **Documents**
   - Upload a PDF document
   - Verify it appears in the document list
   - Check that `indexed: true` (backend auto-indexes)
   - Delete a document and verify removal

2. **Queries**
   - Submit a query
   - Verify response appears (one of three modes)
   - Check citations display (for direct_answer mode)
   - Verify new conversation appears in sidebar

3. **Conversations**
   - Click on a conversation in sidebar
   - Verify full conversation history loads
   - Submit a new query within conversation
   - Verify it's added to the same conversation

4. **API Errors**
   - Check browser console for any API errors
   - Verify toast notifications appear on failures
   - Confirm graceful degradation (empty states, error messages)

## Common Issues & Solutions

### CORS Errors
If you see CORS errors in the console:
- Ensure backend has CORS configured for frontend origin
- Check that `VITE_API_BASE_URL` is correct

### 404 Not Found
- Verify backend server is running
- Check that API endpoint paths match backend routes
- Confirm tenant_id matches backend expectations

### Empty Lists
- Check browser console for API errors
- Verify backend has data for the tenant
- Ensure backend persistence database exists

### Type Errors
- Backend response shape may have changed
- Check `/src/app/types/api.ts` matches current backend
- Verify JSON parsing in API client for nested fields

## Production Considerations

Before deploying to production:

1. **Environment Configuration**
   - Set `VITE_API_BASE_URL` to production backend URL
   - Configure proper CORS policies
   - Use HTTPS for all API calls

2. **Authentication**
   - Implement JWT token storage (localStorage/sessionStorage)
   - Add token refresh logic
   - Handle 401/403 responses
   - Implement proper sign-in/sign-out flows

3. **Error Handling**
   - Add retry logic for transient failures
   - Implement proper error boundaries
   - Log errors to monitoring service
   - Show user-friendly error messages

4. **Performance**
   - Consider adding request caching
   - Implement pagination for large lists
   - Add loading states for better UX
   - Optimize conversation list rendering

## File Structure

```
/src/app/
  services/
    api.ts          # Real API client implementation
    mockApi.ts      # Original mock (now unused)
  types/
    api.ts          # Backend-aligned TypeScript types
  App.tsx           # Main app with API integration
  components/       # UI components (unchanged, consume API data)
```

## Next Steps

This integration provides a fully functional frontend that communicates with the P1 backend. The frontend is now ready for:

1. Local development and testing against real backend
2. Export and deployment to your own infrastructure
3. Further enhancements and feature additions
4. Production deployment after auth configuration

All UI components remain unchanged - only the data layer has been wired to use real API calls instead of mock data.
