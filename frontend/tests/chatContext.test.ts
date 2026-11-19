import { test } from 'node:test';
import assert from 'node:assert/strict';
import { contextFiles, toggleRetryFile, sameContext } from '../src/chatContext.ts';
test('active file follows editor and manual files remain',()=>{
  assert.deepEqual(contextFiles(['test.java'],'a.java',[]),['test.java','a.java']);
  assert.deepEqual(contextFiles(['test.java'],'b.java',[]),['test.java','b.java']);
});
test('excluded active file stays excluded and duplicates are removed',()=>{
  assert.deepEqual(contextFiles(['test.java'],'a.java',['a.java']),['test.java']);
  assert.deepEqual(contextFiles(['a.java'],'a.java',[]),['a.java']);
});
test('manual context is preserved at the file limit',()=>{
  const manual=Array.from({length:8},(_,i)=>`${i}.java`);
  assert.deepEqual(contextFiles(manual,'extra.java',[]),manual);
});

test('retry context edits are independent of the original and composer',()=>{
  const original=['a.java'];
  const composer=['other.java'];
  const retry=toggleRetryFile(original,'test.java');
  assert.deepEqual(retry,['a.java','test.java']);
  assert.deepEqual(original,['a.java']);
  assert.deepEqual(composer,['other.java']);
  assert.deepEqual(toggleRetryFile(retry,'a.java'),['test.java']);
});
test('retry context respects the limit and detects changed or cleared context',()=>{
  const full=Array.from({length:8},(_,i)=>`${i}.java`);
  assert.deepEqual(toggleRetryFile(full,'extra.java'),full);
  assert.equal(sameContext(['a','b'],['b','a']),true);
  assert.equal(sameContext(['a'],[]),false);
  assert.equal(sameContext([],[]),true);
});

test('split context preserves manual files, exclusions and uniqueness',()=>{
  assert.deepEqual(contextFiles(['pom.xml'],['Main.java','Calculator.java','Main.java'],[]),['pom.xml','Main.java','Calculator.java']);
  assert.deepEqual(contextFiles([],['Main.java','Calculator.java'],['Main.java']),['Calculator.java']);
  assert.deepEqual(contextFiles(['Main.java'],['Main.java','Calculator.java'],[]),['Main.java','Calculator.java']);
});
