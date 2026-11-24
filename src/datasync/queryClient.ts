import { QueryClient } from '@tanstack/react-query';
import { ServerConnection } from '@jupyterlab/services';
import { URLExt } from '@jupyterlab/coreutils';

export const queryClient = new QueryClient();

export const queryKeys = {
  engineCatalog: ['engineCatalog'] as const,
  contextWindow: ['contextWindow'] as const,
  conversations: (limit: number) => ['conversations', limit] as const,
  conversationMessages: (id: string) =>
    ['conversationMessages', id] as const,
};

export const getSettings = () => ServerConnection.makeSettings();

export function buildRequest(endpoint: string, init?: RequestInit) {
  const settings = getSettings();
  return ServerConnection.makeRequest(
    URLExt.join(settings.baseUrl, endpoint),
    init ?? {},
    settings
  );
}