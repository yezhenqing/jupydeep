/**
 * Adapted from 'ai-chat-ui' by Pydantic.
 * * Source: https://github.com/pydantic/ai-chat-ui/blob/main/src/Part.tsx
 * License: MIT (or check their LICENSE file)
 * * Acknowledgment to the original authors for the architectural pattern.
 */

import {
  Message,
  MessageContent
} from '../../../components/ai-elements/message';

import { Actions, Action } from '../../../components/ai-elements/actions';
import { Response } from '../../../components/ai-elements/response';

import { RefreshCcwIcon } from 'lucide-react';
import type {
  UIDataTypes,
  UIMessagePart,
  UITools,
  UIMessage,
  ChatAddToolApproveResponseFunction
} from 'ai';

import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger
} from '../../../components/ai-elements/reasoning';

import { ToolPart } from './tool-part';

/*
import {
  Tool,
  ToolHeader,
  ToolInput,
  ToolOutput,
  ToolContent
} from '../../../components/ai-elements/tool';
import { CodeBlock } from '../../../components/ai-elements/code-block';
*/

interface IPartProps {
  part: UIMessagePart<UIDataTypes, UITools>;
  message: UIMessage;
  status: string;
  regen: (id: string) => void;
  index: number;
  lastMessage: boolean;
  onApprovalResponse: ChatAddToolApproveResponseFunction;
  isEditing?: boolean;
  editDraft?: string;
  onStartEdit?: (messageId: string) => void;
  onCancelEdit?: (messageId: string, draft: string) => void;
  onSubmitEdit?: (messageId: string, newText: string) => void;
  messageIndex?: number;
}

export function Part({
  part,
  message,
  status,
  regen,
  index,
  lastMessage,
  onApprovalResponse,
  isEditing,
  editDraft,
  onStartEdit,
  onCancelEdit,
  onSubmitEdit,
  messageIndex
}: IPartProps) {
  if (part.type === 'text') {
    return (
      <div className="py-1">
        <Message from={message.role}>
          <MessageContent>
            <Response>{part.text}</Response>
          </MessageContent>
        </Message>
        {message.role === 'assistant' && index === message.parts.length - 1 && (
          <Actions className="mt-1">
            <Action
              onClick={() => {
                regen(message.id);
              }}
              label="Retry"
            >
              <RefreshCcwIcon className="size-3" />
            </Action>
          </Actions>
        )}
      </div>
    );
  } else if (part.type === 'reasoning') {
    return (
      <Reasoning
        className="w-full"
        isStreaming={
          status === 'streaming' &&
          index === message.parts.length - 1 &&
          lastMessage
        }
      >
        <ReasoningTrigger />
        <ReasoningContent>{part.text}</ReasoningContent>
      </Reasoning>
    );
  } else if (part.type === 'dynamic-tool' || 'toolCallId' in part) {
    return <ToolPart part={part} onApprovalResponse={onApprovalResponse} />;
  }
}
