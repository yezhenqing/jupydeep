import { useMemo, useCallback, useState } from 'react';
import { useQuery, useMutation, skipToken } from '@tanstack/react-query';
import { queryClient, queryKeys } from './queryClient';
import {
  fetchEngine,
  testMlflowConnection,
  fetchConversations,
  fetchConversationMessages,
  deleteConversation as deleteConversationApi,
  type IContextWindowData,
  type IMlflowTestRequest,
  type IConversationSummary,
  type IConversationMessages
} from './api';
import { useSSE } from './sse';

export function useEngineCatalog() {
  useSSE();
  return useQuery({
    queryKey: queryKeys.engineCatalog,
    queryFn: fetchEngine,
    staleTime: Infinity,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true
  });
}

export function useContextWindow() {
  useSSE();
  return useQuery<IContextWindowData>({
    queryKey: queryKeys.contextWindow,
    queryFn: skipToken,
    staleTime: Infinity
  });
}

export function useMlflowTest() {
  return useMutation({ mutationFn: testMlflowConnection });
}


export const NEW_CONVERSATION_ID = '__new__';

export interface IConversationOption {
  id: string;
  title: string;
  isNew?: boolean;
}

const NEW_CONVERSATION_OPTION: IConversationOption = {
  id: NEW_CONVERSATION_ID,
  title: '+ New Conversation -- JupyDeep AI Partner',
  isNew: true
};

export function useConversation(limit = 50) {
  const [selectedId, setSelectedId] = useState<string>(NEW_CONVERSATION_ID);

  const listQuery = useQuery({
    queryKey: queryKeys.conversations(limit),
    queryFn: () => fetchConversations(limit),
    staleTime: 30_000,
    refetchOnWindowFocus: true
  });

  const isNew = selectedId === NEW_CONVERSATION_ID;

  const options: IConversationOption[] = useMemo(() => {
    const list = listQuery.data?.conversations ?? [];
    return [
      NEW_CONVERSATION_OPTION,
      ...list.map(c => ({
        id: c.conversation_id,
        title: c.title ?? '(untitled)'
      }))
    ];
  }, [listQuery.data]);

  const selected = useMemo<IConversationOption>(() => {
    return options.find(o => o.id === selectedId) ?? NEW_CONVERSATION_OPTION;
  }, [options, selectedId]);

  const select = useCallback((id: string) => {
    setSelectedId(id);

    if (!id || id === NEW_CONVERSATION_ID) {
      return;
    }

    void queryClient.invalidateQueries({
      queryKey: queryKeys.conversationMessages(id),
      exact: true
    });
  }, []);

  const selectNew = useCallback(() => {
    setSelectedId(NEW_CONVERSATION_ID);
  }, []);

  const messagesQuery = useQuery<IConversationMessages>({
    queryKey: queryKeys.conversationMessages(selectedId),
    queryFn: () => fetchConversationMessages(selectedId),
    enabled: !isNew,
    staleTime: Infinity,
    refetchOnMount: false,
    refetchOnWindowFocus: false
  });

  const bindNewConversation = useCallback(
    (realId: string, title: string | null) => {
      queryClient.setQueryData(
        queryKeys.conversationMessages(realId),
        {
          conversation_id: realId,
          title,
          messages: []
        } satisfies IConversationMessages
      );
      setSelectedId(realId);
      queryClient.invalidateQueries({
        queryKey: queryKeys.conversations(limit)
      });
    },
    [limit]
  );

  const deleteConversation = useCallback(
    async (id: string) => {
      const targetId = id.trim();
      if (!targetId || targetId === NEW_CONVERSATION_ID) {
        if (selectedId === targetId) {
          setSelectedId(NEW_CONVERSATION_ID);
        }
        return;
      }

      await deleteConversationApi(targetId);

      queryClient.removeQueries({
        queryKey: queryKeys.conversationMessages(targetId),
        exact: true
      });

      queryClient.setQueriesData<{ conversations?: IConversationSummary[] }>(
        { queryKey: ['conversations'] },
        old => {
          if (!old?.conversations) {
            return old;
          }
          return {
            ...old,
            conversations: old.conversations.filter(
              c => (c.conversation_id ?? c.id) !== targetId
            )
          };
        }
      );

      if (selectedId === targetId) {
        setSelectedId(NEW_CONVERSATION_ID);
      }

      void queryClient.invalidateQueries({
        queryKey: queryKeys.conversations(limit)
      });
    },
    [selectedId, limit]
  );

  return {
    options,
    isLoadingList: listQuery.isLoading,
    listError: listQuery.error,
    refetchList: listQuery.refetch,

    selected,
    selectedId,
    isNew,
    select,
    selectNew,
    deleteConversation,

    messages: messagesQuery.data?.messages ?? [],
    isLoadingMessages: messagesQuery.isLoading,
    messagesError: messagesQuery.error,

    bindNewConversation

  };
}

export type { IContextWindowData, IMlflowTestRequest, IConversationSummary };