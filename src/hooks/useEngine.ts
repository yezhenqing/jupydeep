import { QueryClient, useQuery, skipToken } from '@tanstack/react-query';
import { ServerConnection } from '@jupyterlab/services';
import { URLExt } from '@jupyterlab/coreutils';
import { useEffect } from 'react';

export const queryClient = new QueryClient();

// Query Keys
export const ENGINE_QUERY_KEY = ['engineCatalog'];
export const CONTEXT_QUERY_KEY = ['contextWindow'];

let globalEventSource: EventSource | null = null;
let refCount = 0;

const getSettings = () => ServerConnection.makeSettings();

export function setupSSE() {
  if (globalEventSource) {
    refCount++;
    return;
  }
  refCount = 1;

  const settings = getSettings();
  const sseUrl = URLExt.join(settings.baseUrl, 'jupydeep/engine-sse');
  const urlWithToken = `${sseUrl}?token=${settings.token}`;

  globalEventSource = new EventSource(urlWithToken);

  globalEventSource.onopen = () => {
    queryClient.invalidateQueries({ queryKey: ENGINE_QUERY_KEY });
    queryClient.invalidateQueries({ queryKey: CONTEXT_QUERY_KEY });
  };

  globalEventSource.onmessage = event => {
    try {
      const message = JSON.parse(event.data);
      // console.log("SSE message:", message)
      const eventType = message.event;
      const payload = message.payload;
      switch (eventType) {
        case 'context_updated':
          if (payload) {
            queryClient.setQueryData(CONTEXT_QUERY_KEY, (old: any) => ({
              ...old,
              ...payload
            }));
          }
          break;

        case 'catalog_updated':
        case 'agent_spawned':
          if (payload) {
            queryClient.setQueryData(ENGINE_QUERY_KEY, (old: any) => ({
              ...old,
              ...payload,
              agents: payload.agents ?? old?.agents ?? {}
            }));
          } else {
            queryClient.invalidateQueries({ queryKey: ENGINE_QUERY_KEY });
          }
          break;

        default:
          queryClient.invalidateQueries({ queryKey: ENGINE_QUERY_KEY });
          break;
      }
    } catch (err) {
      console.error('JupyDeep SSE data parse error:', err);
    }
  };

  globalEventSource.onerror = () => {
    console.warn('JupyDeep SSE connection lost, waiting for auto-reconnect...');
  };
}

export function closeSSE() {
  refCount--;
  if (refCount <= 0 && globalEventSource) {
    globalEventSource.onmessage = null;
    globalEventSource.onerror = null;
    globalEventSource.close();
    globalEventSource = null;
    refCount = 0;
  }
}

// ============================================================================
// API Fetchers
// ============================================================================

export const fetchEngine = async () => {
  const settings = getSettings();
  const fetchUrl = URLExt.join(settings.baseUrl, 'jupydeep/catalog');

  const response = await ServerConnection.makeRequest(
    fetchUrl,
    { method: 'GET' },
    settings
  );

  if (!response.ok) {
    throw new Error('JupyDeep: Unable to get server configuration');
  }

  return await response.json();
};

// ============================================================================
// Custom React Hooks
// ============================================================================

export function useEngineCatalog() {
  useEffect(() => {
    setupSSE();
    return () => closeSSE();
  }, []);

  return useQuery({
    queryKey: ENGINE_QUERY_KEY,
    queryFn: fetchEngine,
    staleTime: Infinity,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true
  });
}

export interface IContextWindowData {
  current?: number;
  pct?: number;
  maximum?: number;
}

export function useContextWindow() {
  useEffect(() => {
    setupSSE();
    return () => closeSSE();
  }, []);

  return useQuery<IContextWindowData>({
    queryKey: CONTEXT_QUERY_KEY,
    // No REST API to fetch data; entirely written externally via SSE from server.
    // purely push mode
    queryFn: skipToken,
    staleTime: Infinity
  });
}
