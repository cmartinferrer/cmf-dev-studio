export type WorkspacePreferences = {
  explorerVisible: boolean;
  assistantVisible: boolean;
  explorerWidth: number;
  assistantWidth: number;
  terminalHeight: number;
};
export const preferencesKey = 'cmf.workspace.layout.v1';
export const defaults: WorkspacePreferences = {
  explorerVisible: true, assistantVisible: true,
  explorerWidth: 225, assistantWidth: 355, terminalHeight: 240,
};
export function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}
export function parsePreferences(raw: string | null): WorkspacePreferences {
  try {
    const value = JSON.parse(raw ?? 'null');
    if (!value || typeof value !== 'object') return {...defaults};
    const bool = (key: 'explorerVisible' | 'assistantVisible') => typeof value[key] === 'boolean' ? value[key] : defaults[key];
    const size = (key: 'explorerWidth' | 'assistantWidth' | 'terminalHeight', min: number, max: number) => typeof value[key] === 'number' && Number.isFinite(value[key]) ? clamp(value[key], min, max) : defaults[key];
    return {explorerVisible: bool('explorerVisible'), assistantVisible: bool('assistantVisible'), explorerWidth: size('explorerWidth',150,420), assistantWidth: size('assistantWidth',270,650), terminalHeight: size('terminalHeight',130,520)};
  } catch { return {...defaults}; }
}
export function loadPreferences(): WorkspacePreferences {
  try { return parsePreferences(localStorage.getItem(preferencesKey)); }
  catch { return {...defaults}; }
}
export function savePreferences(value: WorkspacePreferences) {
  try { localStorage.setItem(preferencesKey, JSON.stringify(value)); } catch { /* Storage may be unavailable. */ }
}
