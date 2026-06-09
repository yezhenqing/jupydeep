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
//import { Progress } from '../ui/progress';

import { Part } from './parts/Part';
import { ToolUIPart } from 'ai';

import { Bot as BotIcon } from 'lucide-react';
import { useCallback, useState, useRef, useEffect, useMemo } from 'react';
import { toast } from 'sonner';

import { DefaultChatTransport } from 'ai';
import { useChat } from '@ai-sdk/react';
import { ServerConnection } from '@jupyterlab/services';
import { useEngineCatalog } from '../../hooks/useEngine';

const settings = ServerConnection.makeSettings();

const ChatBot = () => {
  const { data: engineData, isLoading } = useEngineCatalog();
  const [agents, setAgents] = useState<string[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>('');

  useEffect(() => {
    if (!isLoading && engineData?.payload?.agents) {
      const agentList = Object.keys(engineData.payload.agents).filter(
        key => engineData.payload.agents[key].enabled
      );

      setAgents(agentList);

      if (agentList.length > 0) {
        if (!agentList.includes(selectedAgent)) {
          if (engineData?.payload?.default_agent) {
            setSelectedAgent(engineData.payload.default_agent);
          } else {
            setSelectedAgent(agentList[0]);
          }
        }
      } else {
        setSelectedAgent('');
      }
    }
  }, [isLoading, engineData]);

  const [text, setText] = useState<string>('');

  const {
    messages,
    sendMessage,
    regenerate,
    status,
    error,
    stop,
    addToolApprovalResponse
  } = useChat({
    transport: new DefaultChatTransport({
      api: '/jupydeep/chat',
      headers: { Authorization: `Token ${settings.token}` }
    }),
    onError: err => toast.error(err.message)
  });

  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const editDraftsRef = useRef(new Map<string, string>());

  const handleSubmit = useCallback(
    (message: PromptInputMessage) => {
      const content = message.text?.trim();
      if (!content && !message.files?.length) {
        return;
      }

      if (!selectedAgent) {
        // must need to have a selected agent
        alert('Please select an agent. Make sure at least one is available.');
        return;
      }

      sendMessage(
        { text: content || 'Sent with attachments' },
        { body: { agent_id: selectedAgent } }
      );
      setText('');
    },
    [sendMessage, selectedAgent]
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
          {messages.map((message, msgIndex) => (
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
          ))}

          <div className="min-h-8 flex items-center px-4 shrink-0 justify-center">
            {
              /*status === 'submitted'*/ shouldShowLoader ? (
                <Loader size={12} />
              ) : (
                <div className="h-[12px]" />
              )
            }
          </div>

          {status === 'error' && error && (
            <div className="px-4 py-3 mx-4 my-2 bg-destructive/10 border border-destructive/20 rounded-md text-destructive text-sm">
              <strong>System Error: </strong>{' '}
              {error.message
                ? error.message // first line  error.message.split('\n')[0]
                : 'Request failed. Please try again.'}
            </div>
          )}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <Separator orientation="horizontal" />
      {/* TODO: Implement context window consumption tracker */}
      {/*  <Progress value={56} className="w-full" />

      <div className="flex items-center gap-2 px-2">
        <span>
          You used <strong>$0.50</strong> in this turn
        </span>
        <Separator orientation="vertical" className="h-4" />
      </div>
      */}
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
                  onValueChange={newValue =>
                    setSelectedAgent(newValue || 'No items found.')
                  }
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
