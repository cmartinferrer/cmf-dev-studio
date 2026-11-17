import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Pencil, Trash2, X, Paperclip, FolderPlus, FilePlus, Copy, ClipboardPaste } from 'lucide-react';

export type ResourceTarget = { initialAction?:'delete'; copy?:()=>void; paste?:()=>void; newFile?:()=>void; newFolder?:()=>void; addToChat?:()=>void; name:string; x:number; y:number; removeLabel:string; warning:string; rename?:(name:string)=>Promise<void>; remove?:()=>Promise<void> };
export default function ResourceActions({target,onClose}:{target:ResourceTarget;onClose:()=>void}) {
  const [action,setAction]=useState<'rename'|'delete'|null>(target.initialAction??null);
  const [name,setName]=useState(target.name);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const menu=useRef<HTMLDivElement>(null);
  useEffect(()=>{menu.current?.querySelector('button')?.focus();},[]);
  useEffect(()=>{
    const key=(e:KeyboardEvent)=>{if(e.key==='Escape'&&!busy){e.preventDefault();onClose();}};
    const outside=(e:PointerEvent)=>{if(!action&&!menu.current?.contains(e.target as Node))onClose();};
    window.addEventListener('keydown',key);window.addEventListener('pointerdown',outside);
    return()=>{window.removeEventListener('keydown',key);window.removeEventListener('pointerdown',outside);};
  },[action,busy,onClose]);
  async function submit(e:React.FormEvent){e.preventDefault();if(busy)return;setBusy(true);setError('');try{if(action==='rename')await target.rename?.(name.trim());else await target.remove?.();onClose();}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
  if(!action)return createPortal(<div ref={menu} className="resource-menu" style={{left:Math.max(4,Math.min(target.x,window.innerWidth-210)),top:Math.max(4,Math.min(target.y,window.innerHeight-300))}} aria-label="Resource actions">{target.copy&&<button onClick={()=>{target.copy?.();onClose();}}><Copy size={14}/> Copy</button>}{target.paste&&<button onClick={()=>{target.paste?.();onClose();}}><ClipboardPaste size={14}/> Paste</button>}{target.newFile&&<button onClick={()=>{target.newFile?.();onClose();}}><FilePlus size={14}/> New file</button>}{target.newFolder&&<button onClick={()=>{target.newFolder?.();onClose();}}><FolderPlus size={14}/> New folder</button>}{target.addToChat&&<button onClick={()=>{target.addToChat?.();onClose();}}><Paperclip size={14}/> Add to chat</button>}{target.rename&&<button onClick={()=>setAction('rename')}><Pencil size={14}/> Rename</button>}{target.remove&&<button className="resource-danger" onClick={()=>setAction('delete')}><Trash2 size={14}/> {target.removeLabel}</button>}</div>,document.body);
  return createPortal(<div className="overlay" onMouseDown={e=>{if(e.target===e.currentTarget&&!busy)onClose();}}><div className="dialog resource-dialog" role="dialog" aria-modal="true" aria-label={action==='rename'?'Rename':target.removeLabel}><div className="dialog-heading"><h2>{action==='rename'?'Rename':target.removeLabel}</h2><button className="icon-button" aria-label="Close" disabled={busy} onClick={onClose}><X size={18}/></button></div><form onSubmit={e=>void submit(e)}>{action==='rename'?<label>Name<input autoFocus required value={name} onChange={e=>setName(e.target.value)} onFocus={e=>e.target.select()}/></label>:<p>{target.warning}</p>}{error&&<div className="form-error" role="alert">{error}</div>}<div className="dialog-footer"><button type="button" className="secondary" disabled={busy} onClick={onClose}>Cancel</button><button className={action==='delete'?'resource-delete':'primary'} disabled={busy||action==='rename'&&!name.trim()} type="submit">{busy?'Working…':action==='rename'?'Rename':target.removeLabel}</button></div></form></div></div>,document.body);
}
