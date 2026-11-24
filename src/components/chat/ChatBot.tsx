import {
  Conversation,
  ConversationContent,
  ConversationScrollButton
} from '../ai-elements/conversation';

import { Loader } from '../ai-elements/loader';

import type { PromptInputMessage } from '../ai-elements/prompt-input';
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputHeader,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools
} from '../ai-elements/prompt-input';

import {
  Source,
  Sources,
  SourcesContent,
  SourcesTrigger
} from '../ai-elements/sources';

import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList
} from '../ui/combobox';

import { InputGroupAddon } from '../ui/input-group';
import { Separator } from '../ui/separator';
import { Progress } from '../ui/progress';

import { Part } from './parts/Part';
import { ToolUIPart } from 'ai';

import { Bot as BotIcon, Trash2 } from 'lucide-react';
import { useCallback, useState, useRef, useEffect, useMemo } from 'react';
import { toast } from 'sonner';

import { DefaultChatTransport } from 'ai';
import { useChat } from '@ai-sdk/react';
import { ServerConnection } from '@jupyterlab/services';
import { useEngineCatalog, useContextWindow } from '../../datasync';
import type { useConversation } from '../../datasync';

type ConversationState = ReturnType<typeof useConversation>;

interface IChatBotProps {
  conversation: ConversationState;
  onStreamingChange?: (streaming: boolean) => void;
}

interface IConversationDataPart {
  type: 'data-conversation';
  data?: {
    conversation_id?: string;
    title?: string;
  };
  id?: string;
}

const settings = ServerConnection.makeSettings();

const ChatBot = ({ conversation, onStreamingChange }: IChatBotProps) => {
  const {
    selectedId,
    isNew,
    messages: historyMessages,
    isLoadingMessages,
    bindNewConversation
  } = conversation;

  const { data: contextData } = useContextWindow();
  const { data: engineData, isLoading } = useEngineCatalog();

  const agents = useMemo(() => {
    const rawAgents = engineData?.payload?.agents;
    if (!rawAgents) {
      return [];
    }
    return Object.keys(rawAgents).filter(key => rawAgents[key]?.enabled);
  }, [engineData]);

  const [selectedAgent, setSelectedAgent] = useState<string>('');

  useEffect(() => {
    if (isLoading) {
      return;
    }
    if (agents.length === 0) {
      if (selectedAgent !== '') {
        setSelectedAgent('');
      }
      return;
    }
    if (!selectedAgent || !agents.includes(selectedAgent)) {
      const preferred = engineData?.payload?.default_agent;
      const nextAgent =
        preferred && agents.includes(preferred) ? preferred : agents[0];
      setSelectedAgent(nextAgent);
    }
  }, [isLoading, agents, engineData?.payload?.default_agent, selectedAgent]);

  const selectedAgentRef = useRef<string>(selectedAgent);
  selectedAgentRef.current = selectedAgent;

  const [text, setText] = useState<string>('');

  const activeConvIdRef = useRef<string | null>(isNew ? null : selectedId);

  const handleDataPart = useCallback(
    (part: unknown) => {
      const dataPart = part as IConversationDataPart | undefined;
      if (dataPart?.type === 'data-conversation') {
        const newConvId = dataPart.data?.conversation_id?.trim();
        if (newConvId) {
          activeConvIdRef.current = newConvId;
          bindNewConversation(newConvId, dataPart.data?.title ?? null);
        }
      }
    },
    [bindNewConversation]
  );

  const {
    messages,
    sendMessage,
    regenerate,
    status,
    error,
    stop,
    addToolApprovalResponse,
    setMessages
  } = useChat({
    transport: new DefaultChatTransport({
      api: '/jupydeep/chat',
      headers: { Authorization: `Token ${settings.token}` },
      prepareSendMessagesRequest: ({ messages, body }) => {
        return {
          body: {
            ...body,
            id: activeConvIdRef.current ?? undefined,
            agent_id: selectedAgentRef.current,
            messages: messages.slice(-1)
          }
        };
      }
    }),
    onData: handleDataPart,
    onError: err => toast.error(err.message)
  });

  const isStreaming = status === 'streaming' || status === 'submitted';

  useEffect(() => {
    onStreamingChange?.(isStreaming);
  }, [isStreaming, onStreamingChange]);

  useEffect(() => {
    return () => {
      onStreamingChange?.(false);
    };
  }, [onStreamingChange]);

  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  useEffect(() => {
    if (status === 'streaming' || status === 'submitted') {
      return;
    }

    if (isNew) {
      if (activeConvIdRef.current !== null) {
        activeConvIdRef.current = null;
        setMessages([]);
      }
      return;
    }

    if (!selectedId || isLoadingMessages) {
      return;
    }

    if (activeConvIdRef.current !== selectedId) {
      activeConvIdRef.current = selectedId;
      setMessages(historyMessages as any);
    } else if (messagesRef.current.length === 0 && historyMessages.length > 0) {
      setMessages(historyMessages as any);
    }
  }, [
    isNew,
    selectedId,
    historyMessages,
    isLoadingMessages,
    status,
    setMessages
  ]);

  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const editDraftsRef = useRef(new Map<string, string>());

  const handleSubmit = useCallback(
    (message: PromptInputMessage) => {
      const content = message.text?.trim();
      if (!content && !message.files?.length) {
        return;
      }

      if (!selectedAgent) {
        alert('Please select an agent. Make sure at least one is available.');
        return;
      }

      if (!isNew && isLoadingMessages) {
        return;
      }

      sendMessage({ text: content || 'Sent with attachments' });
      setText('');
    },
    [sendMessage, selectedAgent, isNew, isLoadingMessages]
  );

  const handleTextChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      setText(event.target.value);
    },
    []
  );

  function regen(messageId: string) {
    regenerate({ messageId }).catch((error: unknown) => {
      console.error('Error regenerating message:', error);
    });
  }

  const handleStartEdit = useCallback((messageId: string) => {
    setEditingMessageId(messageId);
  }, []);

  const handleCancelEdit = useCallback((messageId: string, draft: string) => {
    editDraftsRef.current.set(messageId, draft);
    setEditingMessageId(null);
  }, []);

  const handleSubmitEdit = useCallback(
    (messageId: string, newText: string) => {
      const original = messages.find(m => m.id === messageId);
      const originalText = original?.parts.find(p => p.type === 'text');
      const unchanged =
        originalText && 'text' in originalText && originalText.text === newText;

      editDraftsRef.current.delete(messageId);
      setEditingMessageId(null);

      if (unchanged) {
        return;
      }
    },
    [messages]
  );

  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const handleClearChat = useCallback(async () => {
    if (isDeleting) {
      return;
    }

    const targetId =
      activeConvIdRef.current ?? (!isNew && selectedId ? selectedId : null);

    if (!targetId && messages.length === 0) {
      return;
    }

    if (isStreaming) {
      stop();
    }

    activeConvIdRef.current = null;
    setMessages([]);
    setText('');

    if (!targetId) {
      return;
    }

    setIsDeleting(true);
    try {
      await conversation.deleteConversation(targetId);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Failed to delete conversation'
      );
    } finally {
      setIsDeleting(false);
    }
  }, [
    isDeleting,
    isNew,
    selectedId,
    messages.length,
    isStreaming,
    stop,
    setMessages,
    conversation
  ]);

  const hasPendingToolCalls = useMemo(() => {
    if (status !== 'streaming') {
      return false;
    }

    const lastAssistantMessage = [...messages]
      .reverse()
      .find(m => m.role === 'assistant');
    if (!lastAssistantMessage?.parts) {
      return false;
    }

    const toolParts = lastAssistantMessage.parts.filter(
      (part): part is ToolUIPart<any> => part.type.startsWith('tool-')
    );

    return toolParts.some(
      part =>
        part.state === 'input-streaming' ||
        part.state === 'input-available' ||
        part.state === 'output-available'
    );
  }, [messages, status]);

  const shouldShowLoader = status === 'submitted' || hasPendingToolCalls;

  return (
    <div className="relative flex h-full flex-col gap-1 overflow-hidden">
      <Conversation className="flex-1 overflow-y-auto">
        <ConversationContent>
          {!isNew && isLoadingMessages ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              Loading conversation history...
            </div>
          ) : (
            messages.map((message, msgIndex) => (
              <div
                key={message.id}
                style={{ color: 'var(--jp-ui-font-color1)' }}
                className={`
                  group/user-message transition-colors w-full px-2 py-1
                  ${message.role === 'user' ? 'text-right' : 'text-left'}
                `}
              >
                <div className="bg-transparent [&_*]:!text-[var(--jp-ui-font-color1)] [&_*]:!bg-transparent">
                  {message.role === 'assistant' &&
                    message.parts.filter(part => part.type === 'source-url')
                      .length > 0 && (
                      <Sources>
                        <SourcesTrigger
                          count={
                            message.parts.filter(
                              part => part.type === 'source-url'
                            ).length
                          }
                        />
                        {message.parts
                          .filter(part => part.type === 'source-url')
                          .map((part, i) => (
                            <SourcesContent key={`${message.id}-${i}`}>
                              <Source
                                key={`${message.id}-${i}`}
                                href={part.url}
                                title={part.url}
                              />
                            </SourcesContent>
                          ))}
                      </Sources>
                    )}
                  {message.parts.map((part, i) => (
                    <Part
                      key={`${message.id}-${i}`}
                      part={part}
                      message={message}
                      status={status}
                      index={i}
                      regen={regen}
                      lastMessage={message.id === messages.at(-1)?.id}
                      onApprovalResponse={addToolApprovalResponse}
                      isEditing={editingMessageId === message.id}
                      editDraft={editDraftsRef.current.get(message.id)}
                      onStartEdit={handleStartEdit}
                      onCancelEdit={handleCancelEdit}
                      onSubmitEdit={handleSubmitEdit}
                      messageIndex={msgIndex}
                    />
                  ))}
                </div>
              </div>
            ))
          )}

          <div className="min-h-8 flex items-center px-4 shrink-0 justify-center">
            {shouldShowLoader ? (
              <Loader size={12} />
            ) : (
              <div className="h-[12px]" />
            )}
          </div>

          {status === 'error' && error && (
            <div className="px-4 py-3 mx-4 my-2 bg-destructive/10 border border-destructive/20 rounded-md text-destructive text-sm">
              <strong>System Error: </strong>{' '}
              {error.message
                ? error.message
                : 'Request failed. Please try again.'}
            </div>
          )}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <Separator orientation="horizontal" className="shrink-0" />
      {/* Context window consumption tracker */}
      <div className="w-full shrink-0 px-2 py-1 box-border">
        <div className="flex w-full items-center gap-1.5">
          <span
            style={{ color: 'var(--jp-ui-font-color2)' }}
            className="text-[10px] leading-none font-medium whitespace-nowrap shrink-0 select-none"
          >
            Context Window ({(contextData?.pct ?? 0).toFixed(3)}%):
          </span>
          <Progress
            value={Math.min(contextData?.pct ?? 0, 100)}
            className="flex-1 h-2 bg-[var(--jp-layout-color2)] [&>div]:bg-[var(--jp-brand-color1)]"
          />
        </div>
      </div>

      <div className="flex items-center gap-2 px-2">
        <button
          type="button"
          //onClick={handleClearChat}
          onDoubleClick={handleClearChat}
          disabled={isDeleting || (isNew && messages.length === 0)}
          className="flex items-center justify-center p-2 rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title="Delete conversation & start new session"
        >
          <Trash2 size={16} className="text-muted-foreground" />
        </button>
      </div>

      <div className="flex shrink-0 flex-col p-[2px]">
        <div className="w-full p-0">
          <PromptInput globalDrop multiple onSubmit={handleSubmit}>
            <PromptInputHeader></PromptInputHeader>
            <PromptInputBody>
              <PromptInputTextarea
                onChange={handleTextChange}
                value={text}
                rows={4}
                className="min-h-[100px] resize-none"
              />
            </PromptInputBody>
            <PromptInputFooter>
              <PromptInputTools>
                <Combobox
                  items={agents}
                  value={selectedAgent}
                  onValueChange={newValue => setSelectedAgent(newValue || '')}
                >
                  <ComboboxInput
                    value={isLoading ? 'Loading...' : selectedAgent}
                    disabled={isLoading}
                  >
                    <InputGroupAddon>
                      <BotIcon />
                    </InputGroupAddon>
                  </ComboboxInput>

                  <ComboboxContent
                    side="top"
                    align="start"
                    className="w-max min-w-0"
                  >
                    <ComboboxEmpty>No items found.</ComboboxEmpty>
                    <ComboboxList>
                      {item => (
                        <ComboboxItem
                          key={item}
                          value={item}
                          className="whitespace-nowrap"
                        >
                          {item}
                        </ComboboxItem>
                      )}
                    </ComboboxList>
                  </ComboboxContent>
                </Combobox>
              </PromptInputTools>
              <PromptInputSubmit status={status} onStop={stop} />
            </PromptInputFooter>
          </PromptInput>
        </div>
      </div>
    </div>
  );
};

export default ChatBot;