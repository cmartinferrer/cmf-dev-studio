export type TerminalContext = { id: number; name: string; output: string };
export type TerminalReader = () => string;
export function sanitizeTerminalOutput(value: string): string {
  return value.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '').replace(/\x1b\][^\x07]*(?:\x07|\x1b\\)/g, '')
    .replace(/\b(Bearer)\s+[^\s]+/gi, '$1 [REDACTED]')
    .replace(/\b([\w-]*(?:password|passwd|secret|token|api[_-]?key)[\w-]*)\s*[:=]\s*(?:"[^"]*"|'[^']*'|[^\s]+)/gi, '$1=[REDACTED]')
    .replace(/\b(?:AIza[\w-]{35}|gh[pousr]_[\w]+|github_pat_[\w]+|sk-[\w-]{16,})\b/g, '[REDACTED]')
    .split('\n').slice(-200).join('\n').slice(-12000);
}
export function captureTerminal(id: number, name: string, reader?: TerminalReader): TerminalContext | null {
  const output = sanitizeTerminalOutput(reader?.() ?? '');
  return output.trim() ? {id, name: sanitizeTerminalOutput(name).slice(0,80), output} : null;
}

/** Match only existing eligible repository paths at diagnostic locations. */
export function diagnosticFiles(snapshots: TerminalContext[], candidates: {path:string}[]): string[] {
  const result = new Set<string>();
  for (const snapshot of snapshots) {
    for (const line of snapshot.output.split('\n')) {
      const matches = candidates.filter(({path}) => {
        const escaped = path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        return new RegExp('(?:^|[\\s/"\'])'+escaped+'(?=:\\s*\\[?\\d|\\(\\d|["\']\\s*,\\s*line\\s+\\d)').test(line);
      });
      // Prefer the most specific path if one candidate is a suffix of another.
      for (const {path} of matches) {
        if (!matches.some(other=>other.path!==path&&other.path.endsWith('/'+path))) result.add(path);
      }
    }
  }
  return [...result];
}

export function terminalTask(previousTask: string, locale: string): string {
  const spanish = locale.toLowerCase().startsWith('es') || (previousTask ? /\b(crea(?:me)?|haz|anade|quiero|puedes|corrige|implementa|necesito|genera|modifica|arregla|analiza|error de|ficheros)\b/i.test(previousTask.normalize('NFD').replace(/\p{M}/gu,'')) : false);
  return spanish ? 'Analiza el error de la terminal y corrige su causa en los ficheros afectados.' : 'Analyze the terminal error and fix its cause in the affected files.';
}
