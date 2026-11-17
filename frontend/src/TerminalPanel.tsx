import { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { Play, Square } from 'lucide-react';

/** Interactive human-controlled PTY. No agent has access to this socket. */
export default function TerminalPanel({projectId,runPath,onConnectionChange}:{projectId:string;runPath?:string;onConnectionChange:(connected:boolean)=>void}) {
  const container=useRef<HTMLDivElement|null>(null);
  const terminal=useRef<Terminal|null>(null);
  const socket=useRef<WebSocket|null>(null);
  const fit=useRef<FitAddon|null>(null);
  const [running,setRunning]=useState(false);
  const [error,setError]=useState('');
  const [connected,setConnected]=useState(false);
  useEffect(()=>{
    if(!container.current)return;
    const term=new Terminal({cursorBlink:true,convertEol:true,fontSize:12,fontFamily: ['"JetBrainsMono Nerd Font Mono"', '"MesloLGS NF"', '"Droid Sans Mono for Powerline"', '"Meslo LG M for Powerline"', '"DejaVu Sans Mono for Powerline"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'].join(', '),theme:{background:'#0c1320',foreground:'#d7e1f2'},scrollback:3000});
    const addon=new FitAddon();term.loadAddon(addon);term.open(container.current);terminal.current=term;fit.current=addon;
    const resize=()=>{try{addon.fit();if(socket.current?.readyState===WebSocket.OPEN)socket.current.send(JSON.stringify({type:'resize',cols:term.cols,rows:term.rows}));}catch{ /* panel not visible yet */ }};
    const observer=new ResizeObserver(resize);observer.observe(container.current);
    const input=term.onData(data=>{if(socket.current?.readyState===WebSocket.OPEN)socket.current.send(JSON.stringify({type:'input',data}));});
    const frame=requestAnimationFrame(()=>{resize();if(runPath)start(runPath);});
    return()=>{cancelAnimationFrame(frame);socket.current?.close();socket.current=null;input.dispose();observer.disconnect();term.dispose();terminal.current=null;fit.current=null;onConnectionChange(false);};
  },[projectId,runPath]);
  function start(path?:string){
    if(socket.current)return;
    setError('');setConnected(false);setRunning(true);onConnectionChange(true);const protocol=location.protocol==='https:'?'wss:':'ws:';
    const ws=new WebSocket(`${protocol}//${location.host}/api/projects/${encodeURIComponent(projectId)}/terminal${path?`?run=${encodeURIComponent(path)}`:''}`);
    ws.binaryType='arraybuffer';socket.current=ws;
    const decoder=new TextDecoder();
    ws.onopen=()=>{if(socket.current!==ws)return;setConnected(true);setRunning(true);terminal.current?.focus();fit.current?.fit();ws.send(JSON.stringify({type:'resize',cols:terminal.current?.cols??80,rows:terminal.current?.rows??24}));};
    ws.onmessage=e=>{if(socket.current===ws)terminal.current?.write(typeof e.data==='string'?e.data:decoder.decode(e.data,{stream:true}));};
    ws.onerror=()=>{if(socket.current===ws)setError('Could not connect to the local terminal. Check FastAPI.');};
    ws.onclose=()=>{if(socket.current===ws){socket.current=null;setConnected(false);setRunning(false);onConnectionChange(false);}};
  }
  function stop(){if(runPath)terminal.current?.writeln('\r\nStop requested by user.');socket.current?.close();socket.current=null;setConnected(false);setRunning(false);onConnectionChange(false);}
  return <div className="studio-terminal studio-xterm">
    <div className="studio-terminal-actions"><span>{runPath ? `${running ? (connected ? '● Running' : '○ Starting') : '○ Not running'} · ${runPath}` : `${running ? (connected ? '● Connected' : '○ Connecting') : '○ Terminal stopped'} · Local project shell`}</span><div>{!running?<button onClick={()=>start(runPath)}><Play size={13}/> {runPath?'Run again':'Start'}</button>:<button onClick={stop}><Square size={13}/> Stop</button>}</div></div>
    {error&&<div role="alert" className="ide-error">{error}</div>}
    <div className="studio-xterm-surface" ref={container} aria-label="Interactive terminal"/>
    {!running&&!runPath&&<div className="studio-xterm-hint">Press Start to open a shell. Commands run on your computer as your backend user; AI agents cannot use this terminal.</div>}
  </div>;
}
