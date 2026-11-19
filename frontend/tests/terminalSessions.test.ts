import { test } from 'node:test';
import assert from 'node:assert/strict';
import { initialSessions, addSession, selectSession, renameSession, removeSession, colorSession } from '../src/terminalSessions.ts';
test('manual sessions have independent stable identities',()=>{const s=addSession(addSession(initialSessions()));assert.deepEqual(s.sessions.map(t=>t.id),[1,2]);assert.equal(s.active,2);assert.equal(selectSession(s,1).active,1);});
test('run opens independently of manual shells',()=>{const s=addSession(addSession(initialSessions()),'src/Main.java');assert.equal(s.sessions[0].runPath,undefined);assert.equal(s.sessions[1].runPath,'src/Main.java');assert.equal(s.active,2);});
test('rename preserves identity and ignores blank names',()=>{const s=addSession(initialSessions());assert.equal(renameSession(s,1,' Backend ').sessions[0].name,'Backend');assert.deepEqual(renameSession(s,1,' '),s);});
test('closing active session selects a neighbor',()=>{const s=addSession(addSession(addSession(initialSessions())));assert.equal(removeSession(s,3).active,2);assert.equal(removeSession(selectSession(s,2),2).active,3);});
test('closing inactive session preserves selection',()=>{const s=addSession(addSession(initialSessions()));assert.equal(removeSession(s,1).active,2);});
test('closing last session clears selection and never reuses id',()=>{const s=removeSession(addSession(initialSessions()),1);assert.equal(s.active,null);assert.equal(addSession(s).active,2);});

test("terminal color is independent and preserves session identity",()=>{const s=addSession(addSession(initialSessions()),"Main.java");const colored=colorSession(s,1,"Green");assert.equal(colored.sessions[0].color,"Green");assert.deepEqual(colored.sessions[1],s.sessions[1]);assert.equal(colored.active,s.active);assert.equal(renameSession(colored,1,"Backend").sessions[0].color,"Green");assert.equal(colorSession(colored,1,"Default").sessions[0].color,"Default");});
