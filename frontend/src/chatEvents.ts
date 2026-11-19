import type { ProposalEvent } from './api';

/** Keep internal handoffs out of the conversation, including legacy events. */
export function visibleChatEvents(events: ProposalEvent[]): ProposalEvent[] {
  return events.filter(event =>
    !['requested', 'agent_stage', 'exploration_tool', 'skill_selected', 'investigation_completed'].includes(event.kind) &&
    !(event.kind === 'assistant_response' && ['patch', 'quick_patch'].includes(event.details.action ?? ''))
  );
}

/** Explain review mode and outcome without adding conversational messages. */
export function activityStageLabel(stage: string | undefined, t: (en: string, es: string) => string): string {
  switch (stage) {
    case 'recommendation_full': return t('Recommendation review: full', 'Revisión de recomendaciones: completa');
    case 'recommendation_critical_only': return t('Recommendation review: critical only', 'Revisión de recomendaciones: solo críticas');
    case 'recommendation_result_critical': return t('Review: critical finding', 'Revisión: hallazgo crítico');
    case 'recommendation_result_optional': return t('Review: optional advice', 'Revisión: recomendación opcional');
    case 'recommendation_result_none': return t('Review: no findings', 'Revisión: sin hallazgos');
    case 'recommendation_result_failed': return t('Review: failed', 'Revisión: fallida');
    case 'recommendation_result_skipped': return t('Review: skipped (context budget)', 'Revisión: omitida (límite de contexto)');
    default: return stage ?? '';
  }
}
