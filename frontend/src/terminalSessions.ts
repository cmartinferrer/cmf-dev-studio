export const terminalColors = { Default: "", Blue: "#60a5fa", Green: "#4ade80", Amber: "#fbbf24", Purple: "#c084fc", Red: "#f87171", Cyan: "#22d3ee" } as const;
export type TerminalColor = keyof typeof terminalColors;
export type TerminalSession = { id: number; name: string; runPath?: string; color?: TerminalColor };
export type TerminalSessions = { sessions: TerminalSession[]; active: number | null; nextId: number };
export const initialSessions = (): TerminalSessions => ({sessions: [], active: null, nextId: 1});
export function addSession(state: TerminalSessions, runPath?: string): TerminalSessions {
  const id = state.nextId;
  const name = runPath ? `Run: ${runPath.split('/').pop()}` : `Terminal ${id}`;
  return {sessions: [...state.sessions, {id, name, runPath}], active: id, nextId: id + 1};
}
export function selectSession(state: TerminalSessions, id: number): TerminalSessions {
  return state.sessions.some(s => s.id === id) ? {...state, active: id} : state;
}
export function renameSession(state: TerminalSessions, id: number, name: string): TerminalSessions {
  const trimmed = name.trim();
  return trimmed ? {...state, sessions: state.sessions.map(s => s.id === id ? {...s, name: trimmed} : s)} : state;
}
export function removeSession(state: TerminalSessions, id: number): TerminalSessions {
  const index = state.sessions.findIndex(s => s.id === id);
  if (index < 0) return state;
  const sessions = state.sessions.filter(s => s.id !== id);
  return {...state, sessions, active: state.active === id ? (sessions[Math.min(index, sessions.length - 1)]?.id ?? null) : state.active};
}

export function colorSession(state: TerminalSessions, id: number, color: TerminalColor): TerminalSessions {
  return {...state, sessions: state.sessions.map(s => s.id === id ? {...s, color} : s)};
}
