import { useEffect } from 'react';
import { URLExt } from '@jupyterlab/coreutils';
import { queryClient, queryKeys, getSettings } from './queryClient';

let source: EventSource | null = null;
let refCount = 0;

function acquireSSE() {
  if (source) {
    refCount++;
    return;
  }
  refCount = 1;

  const settings = getSettings();
  const sseUrl = URLExt.join(settings.baseUrl, 'jupydeep/engine-sse');
  const es = new EventSource(`${sseUrl}?token=${settings.token}`);
  source = es;

  es.onopen = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.engineCatalog });
    queryClient.invalidateQueries({ queryKey: queryKeys.contextWindow });
  };

  es.onmessage = e => {
    try {
      //console.log("SSE message:", e.data)
      const { event, payload } = JSON.parse(e.data);
      const handler = HANDLERS[event] ?? HANDLERS.__default;
      handler?.(payload);
    } catch (err) {
      console.error('JupyDeep SSE parse error:', err);
    }
  };

  es.onerror = () => {
    console.warn('JupyDeep SSE connection lost, auto-reconnecting...');
    queryClient.invalidateQueries({ queryKey: queryKeys.engineCatalog });
  };
}

function releaseSSE() {
  refCount--;
  if (refCount > 0 || !source) {
    return;
  }
  source.onopen = null;
  source.onmessage = null;
  source.onerror = null;
  source.close();
  source = null;
  refCount = 0;
}

type Handler = (payload: any) => void;

const mergeEngine: Handler = payload => {
  if (!payload) {
    queryClient.invalidateQueries({ queryKey: queryKeys.engineCatalog });
    return;
  }
  queryClient.setQueryData(queryKeys.engineCatalog, (old: any) => ({
    ...old,
    ...payload,
    agents: payload.agents ?? old?.agents ?? {}
  }));
};

const handleConversationTitle: Handler = payload => {
  const conversationId = payload?.conversation_id;
  const title = payload?.title;
  if (!conversationId || typeof title !== 'string') {
    return;
  }

  let matched = false;

  queryClient.setQueriesData<{
    conversations?: Array<{
      conversation_id: string;
      title?: string | null;
      [k: string]: unknown;
    }>;
    [k: string]: unknown;
  }>({ queryKey: ['conversations'] }, old => {
    if (!old?.conversations) {
      return old;
    }
    const nextConversations = old.conversations.map(item => {
      if (item.conversation_id === conversationId) {
        matched = true;
        return { ...item, title };
      }
      return item;
    });
    return matched ? { ...old, conversations: nextConversations } : old;
  });

  if (!matched) {
    void queryClient.invalidateQueries({ queryKey: ['conversations'] });
  }
};

const HANDLERS: Record<string, Handler> = {
  catalog_updated: mergeEngine,
  agent_spawned: mergeEngine,
  context_updated: payload => {
    if (!payload) {
      return;
    }
    queryClient.setQueryData(queryKeys.contextWindow, (old: any) => ({
      ...old,
      ...payload
    }));
  },
  conversation_title: handleConversationTitle,
  __default: () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.engineCatalog });
  }
};

export function useSSE() {
  useEffect(() => {
    acquireSSE();
    return releaseSSE;
  }, []);
}
