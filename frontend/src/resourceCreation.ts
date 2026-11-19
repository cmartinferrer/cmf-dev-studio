/** Resolve the destination of a new resource from a single explorer selection. */
export function creationParent(selection: string[], kind?: string): string {
  if (selection.length !== 1) return '';
  const path = selection[0];
  if (kind === 'directory') return path;
  if (kind === 'file') return path.split('/').slice(0, -1).join('/');
  return '';
}

/** Keep the typed path relative to the chosen destination. */
export function creationPath(parent: string, name: string): string {
  const relative = name.trim();
  if (!relative || /[\\\0]/.test(relative) || relative.split('/').some(part => !part || part.startsWith('.'))) {
    throw new Error('Enter a valid relative file or folder name');
  }
  return parent ? `${parent}/${relative}` : relative;
}
