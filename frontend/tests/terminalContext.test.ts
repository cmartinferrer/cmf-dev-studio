import { test } from 'node:test';
import assert from 'node:assert/strict';
import { captureTerminal, sanitizeTerminalOutput } from '../src/terminalContext.ts';

test('captures only the requested reader and masks credentials', () => {
  const snapshot = captureTerminal(2, 'Run', () => 'ERROR\npassword=example\nBearer example');
  assert.deepEqual(snapshot, {id:2,name:'Run',output:'ERROR\npassword=[REDACTED]\nBearer [REDACTED]'});
  assert.equal(captureTerminal(1,'Empty'),null);
});
test('bounds output and removes ANSI color codes', () => {
  const value = sanitizeTerminalOutput(Array.from({length:300},(_,i)=>String(i)).join('\n'));
  assert.equal(value.split('\n').length,200);
  assert.ok(value.startsWith('100\n'));
  assert.equal(sanitizeTerminalOutput('\x1b[31mERROR\x1b[0m'),'ERROR');
  assert.equal(sanitizeTerminalOutput('x'.repeat(13000)).length,12000);
});

test('identifies Maven diagnostic source instead of the launched file', async () => {
  const {diagnosticFiles, terminalTask} = await import('../src/terminalContext.ts');
  const candidates = [{path:'src/main/java/com/example/Hola.java'}, {path:'src/main/java/com/example/Main.java'}, {path:'Hola.java'}];
  const output = '[ERROR] /home/user/project/src/main/java/com/example/Hola.java:[1,1] reached end of file while parsing';
  assert.deepEqual(diagnosticFiles([{id:1,name:'Run Main.java',output}],candidates),[candidates[0].path]);
  assert.match(terminalTask('Crea una calculadora','en-US'),/^Analiza/);
  assert.match(terminalTask('','es-ES'),/^Analiza/);
});

test('matches Python traceback and ignores unrelated paths', async () => {
  const {diagnosticFiles} = await import('../src/terminalContext.ts');
  const output = '  File "/project/src/app.py", line 12, in main\n File "/outside/secret.py", line 2';
  assert.deepEqual(diagnosticFiles([{id:1,name:'Run',output}],[{path:'src/app.py'}]),['src/app.py']);
});
