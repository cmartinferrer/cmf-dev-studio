import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Plus, Pencil, X, Palette, Terminal, Play, MoreHorizontal, Trash2, Check, ChevronRight } from 'lucide-react';
import TerminalPanel from './TerminalPanel';
import { addSession, selectSession, renameSession, removeSession, colorSession, terminalColors, type TerminalColor, type TerminalSessions } from './terminalSessions';

type Props = { projectId: string; visible: boolean; height: number; state: TerminalSessions; setState: React.Dispatch<React.SetStateAction<TerminalSessions>>; onHide: () => void };
type Menu = { id: number; x: number; y: number };
export default function TerminalWorkspace({projectId, visible, height, state, setState, onHide}: Props) {
  const [editing, setEditing] = useState<number | null>(null);
  const [name, setName] = useState('');
  const [menu, setMenu] = useState<Menu | null>(null);
  const [choosingColor, setChoosingColor] = useState(false);
  const [width, setWidth] = useState(160);
  const menuRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const cancelRename = useRef(false);
  const target = state.sessions.find(s => s.id === menu?.id);
  function finishRename() {
    if (editing !== null && !cancelRename.current) setState(s => renameSession(s, editing, name));
    setEditing(null);
  }
  function openMenu(id: number, x: number, y: number) {
    setChoosingColor(false);
    setMenu({id, x, y});
  }
  useEffect(() => {
    if (!menu) return;
    const outside = (e: PointerEvent) => { if (!menuRef.current?.contains(e.target as Node)) setMenu(null); };
    const escape = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); setMenu(null); } };
    const close = () => setMenu(null);
    window.addEventListener('pointerdown', outside);
    window.addEventListener('keydown', escape);
    window.addEventListener('resize', close);
    return () => { window.removeEventListener('pointerdown', outside); window.removeEventListener('keydown', escape); window.removeEventListener('resize', close); };
  }, [menu]);
  useEffect(() => { if (menu) menuRef.current?.querySelector('button')?.focus(); }, [menu, choosingColor]);
  useEffect(() => { if (!visible) setMenu(null); }, [visible]);
  return <div className="ide-terminal-panel" style={{height, display: visible ? undefined : 'none'}}>
    <div className="ide-terminal-header"><strong>TERMINAL</strong><div className="terminal-header-actions"><button title="New terminal" aria-label="New terminal" onClick={() => setState(s => addSession(s))}><Plus size={15}/></button><button onClick={onHide} title="Hide terminal panel" aria-label="Hide terminal panel"><X size={14}/></button></div></div>
    <div className="terminal-session-body" ref={bodyRef}>
      <div className="terminal-session-content">
        {state.sessions.map(session => <div key={session.id} className="terminal-session-view" style={{display: state.active === session.id ? undefined : 'none'}}><TerminalPanel projectId={projectId} runPath={session.runPath} visible={visible && state.active === session.id}/></div>)}
        {!state.sessions.length && <div className="terminal-empty"><Terminal size={24}/><span>No open terminals</span><button onClick={() => setState(s => addSession(s))}>New terminal</button></div>}
      </div>
      {!!state.sessions.length && <><div className="terminal-list-divider" role="separator" aria-label="Resize terminal list" aria-orientation="vertical" tabIndex={0} onKeyDown={e => {if(e.key === 'ArrowLeft' || e.key === 'ArrowRight'){e.preventDefault();setWidth(w => Math.max(110, Math.min(300, w + (e.key === 'ArrowLeft' ? 10 : -10))));}}} onPointerDown={e => {e.currentTarget.setPointerCapture(e.pointerId);}} onPointerMove={e => {if(e.currentTarget.hasPointerCapture(e.pointerId) && bodyRef.current){setWidth(Math.max(110, Math.min(300, bodyRef.current.getBoundingClientRect().right - e.clientX)));}}}/>
      <div className="terminal-session-list" style={{width}} role="group" aria-label="Terminal sessions">
        {state.sessions.map(session => <div key={session.id} className={`terminal-list-row ${state.active === session.id ? 'terminal-list-active' : ''}`} onContextMenu={e => {e.preventDefault();openMenu(session.id,e.clientX,e.clientY);}}>
          {editing === session.id ? <form className="terminal-rename" onSubmit={e => {e.preventDefault();finishRename();}}><input autoFocus aria-label="Terminal name" value={name} maxLength={80} onFocus={e => e.target.select()} onChange={e => setName(e.target.value)} onBlur={finishRename} onKeyDown={e => {if(e.key === 'Escape'){e.preventDefault();cancelRename.current=true;setEditing(null);}}}/></form> : <button className="terminal-list-select" aria-pressed={state.active === session.id} title={session.name} onClick={() => setState(s => selectSession(s,session.id))} onKeyDown={e => {if(e.key === 'ContextMenu' || (e.shiftKey && e.key === 'F10')){e.preventDefault();const r=e.currentTarget.getBoundingClientRect();openMenu(session.id,r.left,r.bottom);}}}>
            {session.runPath ? <Play size={14} style={{color:terminalColors[session.color ?? 'Default'] || undefined}}/> : <Terminal size={14} style={{color:terminalColors[session.color ?? 'Default'] || undefined}}/>}<span>{session.name}</span>
          </button>}
          {editing !== session.id && <button className="terminal-list-more" aria-label={`Actions for ${session.name}`} title="Terminal actions" onClick={e => {const r=e.currentTarget.getBoundingClientRect();openMenu(session.id,r.right-200,r.bottom);}}><MoreHorizontal size={15}/></button>}
        </div>)}
      </div></>}
    </div>
    {visible && menu && target && createPortal(<div ref={menuRef} className="resource-menu terminal-context-menu" style={{left:Math.max(4,Math.min(menu.x,window.innerWidth-210)),top:Math.max(4,Math.min(menu.y,window.innerHeight-190))}} aria-label={`Actions for ${target.name}`}>
      {!choosingColor ? <><button onClick={() => {cancelRename.current=false;setName(target.name);setEditing(target.id);setMenu(null);}}><Pencil size={14}/> Rename</button><button onClick={() => setChoosingColor(true)}><Palette size={14}/> Change color <ChevronRight className="terminal-menu-arrow" size={13}/></button><div className="terminal-menu-divider"/><button className="resource-danger" onClick={() => {setMenu(null);setState(s => removeSession(s,target.id));}}><Trash2 size={14}/> Kill terminal</button></> : <><div className="terminal-color-heading">Terminal color</div><div className="terminal-color-grid">{(Object.keys(terminalColors) as TerminalColor[]).map(color => <button key={color} className="terminal-color-swatch" title={color} aria-label={color} aria-pressed={(target.color ?? 'Default') === color} style={{background:terminalColors[color] || '#8795aa'}} onClick={() => {setState(s => colorSession(s,target.id,color));setMenu(null);}}>{(target.color ?? 'Default') === color && <Check size={14}/>}</button>)}</div><button onClick={() => setChoosingColor(false)}>Back</button></>}
    </div>,document.body)}
  </div>;
}
