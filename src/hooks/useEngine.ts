import { QueryClient, useQuery } from '@tanstack/react-query';
import { ServerConnection } from '@jupyterlab/services';
import { URLExt } from '@jupyterlab/coreutils';

export const queryClient = new QueryClient();
let globalEventSource: EventSource | null = null;
const getSettings = () => ServerConnection.makeSettings();

export function setupSSE() {
  if (globalEventSource) {
    return;
  }
  const settings = getSettings();
  const sseUrl = URLExt.join(settings.baseUrl, 'jupydeep/engine-sse');
  const urlWithToken = `${sseUrl}?token=${settings.token}`;

  globalEventSource = new EventSource(urlWithToken);

  globalEventSource.onopen = () => {
    queryClient.invalidateQueries({ queryKey: ENGINE_QUERY_KEY });
  };

  globalEventSource.onmessage = event => {
    try {
      const newData = JSON.parse(event.data);
      queryClient.setQueryData(ENGINE_QUERY_KEY, (old: any) => ({
        ...old,
        ...newData
      }));
    } catch (err) {
      console.error('JupyDeep SSE data parse error:', err);
    }
  };

  globalEventSource.onerror = () => {
    console.warn('JupyDeep SSE connection lost, waiting for auto-reconnect...');
  };
}

export function closeSSE() {
  if (globalEventSource) {
    globalEventSource.onmessage = null;
    globalEventSource.onerror = null;
    globalEventSource.close();
    globalEventSource = null;
  }
}


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

  const result = await response.json();
  return result;
};

const ENGINE_QUERY_KEY = ['engineCatalog'];
export function useEngineCatalog() {
  setupSSE();

  return useQuery({
    queryKey: ENGINE_QUERY_KEY,
    queryFn: fetchEngine,
    staleTime: Infinity,
    refetchOnWindowFocus: true
  });
}
