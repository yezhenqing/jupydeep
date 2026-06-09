/**
 * Adapted from 'ai-chat-ui' by Pydantic.
 * * Source: https://github.com/pydantic/ai-chat-ui/blob/main/src/components/tool-approval-prompt.tsx
 * License: MIT (or check their LICENSE file)
 * * Acknowledgment to the original authors for the architectural pattern.
 */

import {
  Confirmation,
  ConfirmationAction,
  ConfirmationActions,
  ConfirmationAccepted,
  ConfirmationRejected,
  ConfirmationRequest,
  ConfirmationTitle
} from '../../../components/ai-elements/confirmation';
import type { ChatAddToolApproveResponseFunction, ToolUIPart } from 'ai';

interface IToolApprovalPromptProps {
  approval: { id: string };
  state: ToolUIPart['state'];
  onApprovalResponse: ChatAddToolApproveResponseFunction;
}

export function ToolApprovalPrompt({
  approval,
  state,
  onApprovalResponse
}: IToolApprovalPromptProps) {
  return (
    <Confirmation approval={approval} state={state}>
      <ConfirmationRequest>
        <ConfirmationTitle>
          This tool requires your approval to run
        </ConfirmationTitle>
        <ConfirmationActions>
          <ConfirmationAction
            onClick={() => {
              void onApprovalResponse({ id: approval.id, approved: true });
            }}
          >
            Approve
          </ConfirmationAction>
          <ConfirmationAction
            variant="destructive"
            onClick={() => {
              void onApprovalResponse({ id: approval.id, approved: false });
            }}
          >
            Deny
          </ConfirmationAction>
        </ConfirmationActions>
      </ConfirmationRequest>
      <ConfirmationAccepted>Approved. Executing tool.</ConfirmationAccepted>
      <ConfirmationRejected>Denied. Tool will not run.</ConfirmationRejected>
    </Confirmation>
  );
}
