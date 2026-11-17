import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chatDay,chatTime} from '../src/chatDates.ts';
test('formats persisted timestamps in local time',()=>{const value='2026-11-17T17:00:00Z';assert.equal(chatDay(value),new Date(value).toLocaleDateString(undefined,{year:'numeric',month:'long',day:'numeric'}));assert.equal(chatTime(value),new Date(value).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit',hourCycle:'h23'}));});
test('invalid legacy timestamps are not displayed',()=>{assert.equal(chatDay('now'),'');assert.equal(chatTime('now'),'');});

test('uses 24-hour time including midnight',()=>{assert.equal(chatTime(new Date(2026,10,17,19,43).toISOString()),'19:43');assert.equal(chatTime(new Date(2026,10,17,0,5).toISOString()),'00:05');});

test('formats technical activity in 24-hour time with seconds',()=>{assert.equal(chatTime(new Date(2026,10,17,19,47,33).toISOString(),true),'19:47:33');assert.equal(chatTime(new Date(2026,10,17,0,5,9).toISOString(),true),'00:05:09');assert.equal(chatTime('now',true),'');});
