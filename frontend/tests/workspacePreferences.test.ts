import { test } from 'node:test';
import assert from 'node:assert/strict';
import { defaults, parsePreferences, clamp, loadPreferences, savePreferences } from '../src/workspacePreferences.ts';
test('missing or malformed preferences use defaults',()=>{
  for(const raw of [null,'broken','null','42','[]']) assert.deepEqual(parsePreferences(raw),defaults);
});
test('preferences preserve hidden panels and dimensions',()=>{
  const value={...defaults,explorerVisible:false,assistantVisible:false,explorerWidth:300,assistantWidth:500,terminalHeight:350};
  assert.deepEqual(parsePreferences(JSON.stringify(value)),value);
});
test('invalid fields are repaired independently',()=>{
  assert.deepEqual(parsePreferences('{"explorerVisible":"false","assistantVisible":false,"explorerWidth":10,"assistantWidth":999,"terminalHeight":"300"}'),{...defaults,assistantVisible:false,explorerWidth:150,assistantWidth:650});
});
test('resize bounds are enforced',()=>{assert.equal(clamp(100,150,420),150);assert.equal(clamp(500,150,420),420);assert.equal(clamp(250,150,420),250);});
test('storage unavailable does not prevent startup or saving',()=>{assert.deepEqual(loadPreferences(),defaults);assert.doesNotThrow(()=>savePreferences(defaults));});
