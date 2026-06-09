/**
 * Adapted from 'ai-chat-ui' by Pydantic.
 * * Source: https://github.com/pydantic/ai-chat-ui/blob/main/src/components/tool-part.tsx
 * License: MIT (or check their LICENSE file)
 * * Acknowledgment to the original authors for the architectural pattern.
 */

import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput
} from '../../../components/ai-elements/tool';
import { CodeBlock } from '../../../components/ai-elements/code-block';
import { ToolApprovalPrompt } from './tool-approval-prompt';
import type {
  ChatAddToolApproveResponseFunction,
  DynamicToolUIPart,
  ToolUIPart
} from 'ai';
import { useEffect, useState } from 'react';

interface IToolPartProps {
  part: ToolUIPart | DynamicToolUIPart;
  onApprovalResponse: ChatAddToolApproveResponseFunction;
}

export function ToolPart({ part, onApprovalResponse }: IToolPartProps) {
  const [open, setOpen] = useState(part.state === 'approval-requested');

  // Auto-open the card whenever an approval is requested — `defaultOpen` only
  // runs at mount, but the transition into `approval-requested` happens after
  // mount, so the Confirmation prompt would otherwise stay collapsed.
  useEffect(() => {
    if (part.state === 'approval-requested') {
      setOpen(true);
    }
  }, [part.state]);

  const toolName =
    part.type === 'dynamic-tool'
      ? part.toolName
      : part.type.split('-').slice(1).join('-');
  const approval = 'approval' in part ? part.approval : undefined;

  return (
    <Tool data-tool-name={toolName} open={open} onOpenChange={setOpen}>
      {part.type === 'dynamic-tool' ? (
        <ToolHeader
          type={part.type}
          state={part.state}
          toolName={part.toolName}
        />
      ) : (
        <ToolHeader type={part.type} state={part.state} />
      )}
      <ToolContent>
        <ToolInput input={part.input} />
        {approval && (
          <ToolApprovalPrompt
            approval={approval}
            state={part.state}
            onApprovalResponse={onApprovalResponse}
          />
        )}

        {part.state === 'output-available' && (
          <ToolOutput
            output={
              <CodeBlock
                code={JSON.stringify(part.output, null, 2)}
                language="json"
              />
            }
            errorText={undefined}
          />
        )}

        {part.state === 'output-error' && (
          <ToolOutput
            output={undefined}
            errorText={
              part.errorText || 'An error occurred while executing this tool'
            }
          />
        )}
      </ToolContent>
    </Tool>
  );
}
