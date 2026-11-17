export type Group = { id: number; paths: string[]; active: string | null };
export type Layout = { groups: Group[]; focused: number; direction: 'right' | 'down' };
export const initialLayout = (): Layout => ({ groups: [{ id: 0, paths: [], active: null }], focused: 0, direction: 'right' });
export function activate(layout: Layout, path: string, id = layout.focused): Layout {
  return { ...layout, focused: id, groups: layout.groups.map(g => g.id === id ? { ...g, paths: g.paths.includes(path) ? g.paths : [...g.paths, path], active: path } : g) };
}
export function split(layout: Layout, path: string, direction: Layout['direction']): Layout {
  if (layout.groups.length === 2) return activate({ ...layout, direction }, path, layout.groups.find(g => g.id !== layout.focused)!.id);
  const id = 1 - layout.focused;
  return activate({ ...layout, direction, groups: [...layout.groups, { id, paths: [], active: null }] }, path, id);
}
/** Collapse empty splits while retaining one editor and a valid focused group. */
function collapseEmpty(layout: Layout): Layout {
  const nonempty = layout.groups.filter(group => group.paths.length > 0);
  const groups = nonempty.length ? nonempty : [layout.groups.find(group => group.id === layout.focused) ?? layout.groups[0]];
  const focused = groups.some(group => group.id === layout.focused) ? layout.focused : groups[0].id;
  return { ...layout, groups, focused };
}
export function remove(layout: Layout, id: number, path: string): Layout {
  const groups = layout.groups.map(g => {
    if (g.id !== id) return g;
    const paths = g.paths.filter(p => p !== path);
    return { ...g, paths, active: g.active === path ? paths.at(-1) ?? null : g.active };
  });
  return collapseEmpty({ ...layout, groups });
}
export function moveTab(layout: Layout, from: number, to: number, path: string): Layout {
  if (from === to) return activate(layout, path, to);
  return remove(activate(layout, path, to), from, path);
}
export function closeGroup(layout: Layout, id: number): Layout {
  if (layout.groups.length === 1) return layout;
  const source = layout.groups.find(g => g.id === id)!;
  const target = layout.groups.find(g => g.id !== id)!;
  return { ...layout, focused: target.id, groups: [{ ...target, paths: [...new Set([...target.paths, ...source.paths])], active: target.active ?? source.active }] };
}
export function remap(layout: Layout, keep: (path: string) => boolean, next: (path: string) => string): Layout {
  return collapseEmpty({ ...layout, groups: layout.groups.map(g => {
    const paths = g.paths.filter(keep).map(next);
    return { ...g, paths, active: g.active && keep(g.active) ? next(g.active) : paths.at(-1) ?? null };
  }) });
}

/** One visible document per group, focused document first. */
export function visiblePaths(layout: Layout): string[] {
  const ordered = [...layout.groups].sort((a, b) => Number(b.id === layout.focused) - Number(a.id === layout.focused));
  return [...new Set(ordered.flatMap(group => group.active ? [group.active] : []))];
}
