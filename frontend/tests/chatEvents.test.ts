import { test } from 'node:test';
import assert from 'node:assert/strict';
import { visibleChatEvents } from '../src/chatEvents.ts';
import type { ProposalEvent } from '../src/api.ts';

test('hides internal handoffs while preserving answers, permissions and recommendations', () => {
  const events: ProposalEvent[] = [
    ['assistant_response', 'patch'], ['assistant_response', 'quick_patch'],
    ['investigation_completed', 'patch'], ['agent_stage', ''],
    ['assistant_response', 'answer'], ['assistant_response', 'question'],
    ['assistant_response', 'permission'], ['assistant_response', ''],
    ['assistant_recommendation', ''], ['files_generated', ''], ['tests_passed', ''],
    ['changes_applied', ''], ['generation_failed', ''],
  ].map(([kind, action], sequence) => ({kind, sequence, created_at: '', details: {action}}));
  assert.deepEqual(visibleChatEvents(events).map(event => event.sequence), [4,5,6,7,8,9,10,11,12]);
  assert.equal(events.length, 13);
});
