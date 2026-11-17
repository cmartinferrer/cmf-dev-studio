import { test } from 'node:test';
import assert from 'node:assert/strict';
import { initialLayout, activate, split, remove, moveTab, closeGroup, remap, visiblePaths } from '../src/editorGroups.ts';
test('split duplicates the view and focuses the new group',()=>{const l=split(activate(initialLayout(),'a.py'),'a.py','right');assert.equal(l.focused,1);assert.deepEqual(l.groups.map(g=>g.paths),[['a.py'],['a.py']]);});
test('opening a file affects only the focused group',()=>{const l=activate(split(activate(initialLayout(),'a'),'a','down'),'b');assert.deepEqual(l.groups.map(g=>g.active),['a','b']);});
test('moving a tab preserves other tabs',()=>{const l=moveTab(split(activate(activate(initialLayout(),'a'),'b'),'b','right'),0,1,'a');assert.deepEqual(l.groups.map(g=>g.paths),[['b'],['b','a']]);});
test('closing a view does not close the other view',()=>{const l=remove(split(activate(initialLayout(),'a'),'a','right'),1,'a');assert.deepEqual(l.groups.map(g=>g.active),['a']);});
test('closing a group preserves unique tabs',()=>{const l=closeGroup(activate(split(activate(initialLayout(),'a'),'a','right'),'b'),1);assert.deepEqual(l.groups[0].paths,['a','b']);});
test('rename and deletion affect every view',()=>{const l=split(activate(initialLayout(),'a'),'a','right');const renamed=remap(l,()=>true,()=> 'b');assert.deepEqual(renamed.groups.map(g=>g.active),['b','b']);assert.deepEqual(remap(renamed,()=>false,p=>p).groups.map(g=>g.active),[null]);});

test('visible context includes one active document per group, without duplicates',()=>{
  const l=split(activate(activate(initialLayout(),'hidden.java'),'Main.java'),'Main.java','right');
  assert.deepEqual(visiblePaths(l),['Main.java']);
  const two=activate(l,'Calculator.java');
  assert.deepEqual(visiblePaths(two),['Calculator.java','Main.java']);
  assert.deepEqual(visiblePaths(closeGroup(two,1)),['Main.java']);
});

for (const direction of ['right', 'down'] as const) {
  test(`closing the last tab collapses either panel (${direction})`, () => {
    const layout = activate(split(activate(initialLayout(), 'a'), 'a', direction), 'b');
    const rightOnly = remove(layout, 0, 'a');
    assert.equal(rightOnly.groups.length, 1);
    assert.equal(rightOnly.focused, 1);
    assert.deepEqual(rightOnly.groups[0].paths, ['a', 'b']);
    const leftOnly = remove(remove(layout, 1, 'a'), 1, 'b');
    assert.equal(leftOnly.focused, 0);
    assert.deepEqual(visiblePaths(leftOnly), ['a']);
    const empty = remove(leftOnly, 0, 'a');
    assert.equal(empty.groups.length, 1);
    assert.equal(empty.groups[0].active, null);
    assert.deepEqual(visiblePaths(empty), []);
    assert.equal(split(activate(rightOnly, 'c'), 'c', direction).groups.length, 2);
  });
}
test('moving the last tab collapses its source without losing the document', () => {
  const layout = split(activate(initialLayout(), 'a'), 'a', 'right');
  const result = moveTab(layout, 0, 1, 'a');
  assert.deepEqual(result.groups, [{id: 1, paths: ['a'], active: 'a'}]);
  assert.equal(result.focused, 1);
});
test('deleting the focused panel document restores focus to the remaining panel', () => {
  const layout = remove(activate(split(activate(initialLayout(), 'a'), 'a', 'down'), 'b'), 1, 'a');
  const result = remap(layout, p => p !== 'b', p => p);
  assert.equal(result.focused, 0);
  assert.deepEqual(visiblePaths(result), ['a']);
  assert.equal(result.groups.length, 1);
});
