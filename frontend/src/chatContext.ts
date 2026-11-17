export const MAX_FILES = 8;
export function contextFiles(manual: string[], active: string | string[] | null, excluded: string[]): string[] {
  return [...new Set([...manual, ...(Array.isArray(active) ? active : active ? [active] : []).filter(path => !excluded.includes(path))])].slice(0, MAX_FILES);
}

export function toggleRetryFile(selected: string[], path: string): string[] {
  if (selected.includes(path)) return selected.filter(value => value !== path);
  return selected.length >= MAX_FILES ? selected : [...selected, path];
}

export function sameContext(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every(path => right.includes(path));
}
