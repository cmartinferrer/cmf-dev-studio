import { test } from 'node:test';
import assert from 'node:assert/strict';
import { creationParent, creationPath } from '../src/resourceCreation.ts';

test('a selected package is the creation destination', () => {
  const parent = creationParent(['src/main/java/com/example'], 'directory');
  assert.equal(creationPath(parent, 'Calculator.java'), 'src/main/java/com/example/Calculator.java');
});
test('a selected file uses its containing directory', () => {
  assert.equal(creationParent(['src/main.py'], 'file'), 'src');
  assert.equal(creationParent(['main.py'], 'file'), '');
});
test('no selection, multiple selections and unknown entries use the root', () => {
  assert.equal(creationParent([]), '');
  assert.equal(creationParent(['a', 'b'], 'directory'), '');
  assert.equal(creationParent(['a']), '');
});
test('relative names preserve nested paths and trim surrounding whitespace', () => {
  assert.equal(creationPath('src', '  tests/test_main.py  '), 'src/tests/test_main.py');
  assert.equal(creationPath('', 'main.py'), 'main.py');
});
test('invalid names cannot escape the chosen directory', () => {
  for (const name of ['', ' ', '../main.py', '/main.py', 'a//b', 'a/../b', 'a\\b', '.hidden', 'a/', 'a\0b']) {
    assert.throws(() => creationPath('src', name));
  }
});
