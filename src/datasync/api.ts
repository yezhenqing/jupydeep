import { buildRequest } from './queryClient';
import type { UIMessage } from 'ai';

// ============================================================================
// Types
// ============================================================================

export interface IContextWindowData {
  current?: number;
  pct?: number;
  maximum?: number;
}

export interface IMlflowTestRequest {
  tracking_uri: string;
}

export interface IMlflowTestResponse {
  status: 'success' | 'error';
  message: string;
}

// ============================================================================
// Fetchers
// ============================================================================

export async function fetchEngine() {
  const res = await buildRequest('jupydeep/catalog', { method: 'GET' });
  if (!res.ok) {
    throw new Error('JupyDeep: Unable to get server configuration');
  }
  return res.json();
}

export async function testMlflowConnection(
  data: IMlflowTestRequest
): Promise<IMlflowTestResponse> {
  const res = await buildRequest('jupydeep/mlftest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });

  const result = await res.json();
  if (!res.ok) {
    throw new Error(result.message || 'Failed to connect to MLflow server');
  }
  return result;
}



// ============================================================================
// Conversation section
// ============================================================================
export interface IConversationSummary {
  id: string;
  conversation_id: string;
  title: string | null;
  head_id: string | null;
  revision: number | null;
  updated_at: string | null;
}

export async function fetchConversations(
  limit = 50
): Promise<{ conversations: IConversationSummary[] }> {
  const res = await buildRequest(
    `jupydeep/conversations?limit=${limit}`,
    { method: 'GET' }
  );
  if (!res.ok) {
    throw new Error('JupyDeep: Unable to list conversations');
  }

  const data = await res.json();
  return data;
}


export interface IConversationMessages {
  conversation_id: string;
  title: string | null;
  messages: UIMessage[];
}

export async function fetchConversationMessages(
  conversationId: string
): Promise<IConversationMessages> {
  const res = await buildRequest(
    `jupydeep/conversations/${encodeURIComponent(conversationId)}/messages`,
    { method: 'GET' }
  );

  if (!res.ok) {
    throw new Error(
      `JupyDeep: Unable to load conversation ${conversationId}`
    );
  }

  return res.json();
}

export interface IDeleteConversationResponse {
  deleted: boolean;
  conversation_id: string;
}

export async function deleteConversation(
  conversationId: string
): Promise<IDeleteConversationResponse | null> {
  const res = await buildRequest(
    `jupydeep/conversations/${encodeURIComponent(conversationId)}`,
    { method: 'DELETE' }
  );

  if (res.status === 404) {
    return null;
  }

  if (!res.ok) {
    let message = `JupyDeep: Unable to delete conversation ${conversationId}`;
    try {
      const errData = await res.json();
      if (typeof errData?.error === 'string' && errData.error.trim()) {
        message = errData.error;
      } else if (typeof errData?.message === 'string' && errData.message.trim()) {
        message = errData.message;
      }
    } catch {
   
    }
    throw new Error(message);
  }

  try {
    return await res.json();
  } catch {
    return { deleted: true, conversation_id: conversationId };
  }
}