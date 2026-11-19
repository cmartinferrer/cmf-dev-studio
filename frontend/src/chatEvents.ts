import type { ProposalEvent } from './api';

/** Keep internal handoffs out of the conversation, including legacy events. */
export function visibleChatEvents(events: ProposalEvent[]): ProposalEvent[] {
  return events.filter(event =>
    !['requested', 'agent_stage', 'exploration_tool', 'skill_selected', 'investigation_completed'].includes(event.kind) &&
    !(event.kind === 'assistant_response' && ['patch', 'quick_patch'].includes(event.details.action ?? ''))
  );
}
