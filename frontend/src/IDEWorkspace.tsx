import ResourceActions, { type ResourceTarget } from './ResourceActions';
import { renameEntry, createDirectory, batchEntries, copyEntries } from './api';
import { useCallback, useEffect, useRef, useState } from 'react';
import Editor, { DiffEditor, loader } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';

import EditorWorker from 'monaco-editor/editor/editor.worker.js?worker';
import JsonWorker from 'monaco-editor/language/json/json.worker.js?worker';
import CssWorker from 'monaco-editor/language/css/css.worker.js?worker';
import HtmlWorker from 'monaco-editor/language/html/html.worker.js?worker';
import TsWorker from 'monaco-editor/language/typescript/ts.worker.js?worker';

// Serve Monaco locally via Vite, without depending on an external CDN.
(self as typeof self & { MonacoEnvironment: { getWorker: (_moduleId:string,label:string)=>Worker } }).MonacoEnvironment = { getWorker(_moduleId: string, label: string) {
  if (label === 'json') return new JsonWorker();
  if (label === 'css' || label === 'scss' || label === 'less') return new CssWorker();
  if (label === 'html' || label === 'handlebars' || label === 'razor') return new HtmlWorker();
  if (label === 'typescript' || label === 'javascript') return new TsWorker();
  return new EditorWorker();
} };
loader.config({ monaco });
import { Bot, ChevronDown, ChevronRight, CircleAlert, FileCode, Folder, FolderOpen, FolderPlus, FilePlus, Plus, RefreshCw, Save, MoreHorizontal, Play, X } from 'lucide-react';
import { updateProjectLanguage, type ProjectLanguage, listProjectFiles, openEditableFile, saveEditableFile, previewProposalFile, type FileEntry, type Project, type ProposalChange } from './api';
import AIChat from './AIChat';
import ProjectLanguageIcon from './ProjectLanguageIcon';
import WorkspaceStatusBar from './WorkspaceStatusBar';
import TerminalPanel from './TerminalPanel';
import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, TerminalSquare } from 'lucide-react';

type Tab = { path: string; content: string; saved: string; sha256: string | null; dirty: boolean; isNew: boolean };
type Props = { onDirtyChange:(dirty:boolean)=>void; project: Project; onProjectUpdated: (project: Project) => void; approved: string[]; digest: string | null; onApprove: (paths:string[],digest:string | null)=>void };
function language(path: string) { const ext=path.split('.').pop()?.toLowerCase(); return ({py:'python',ts:'typescript',tsx:'typescript',js:'javascript',jsx:'javascript',json:'json',md:'markdown',yaml:'yaml',yml:'yaml',toml:'ini',java:'java',kt:'kotlin',kts:'kotlin',xml:'xml',gradle:'groovy',html:'html',css:'css'} as Record<string,string>)[ext||''] || 'plaintext'; }
type TreeProps = {projectId:string;path?:string;depth?:number;onOpen:(path:string)=>void;revision:number;onMenu:(e:React.MouseEvent,path:string,isFile?:boolean)=>void;dragged:string[];onDrag:(path:string|null)=>void;onMove:(paths:string[],parent:string)=>void;selection:string[];onSelect:(e:React.MouseEvent,path:string)=>boolean};
function FolderTree({projectId,path='',depth=0,onOpen,revision,onMenu,dragged,onDrag,onMove,selection,onSelect}:TreeProps) {
  const [expanded,setExpanded]=useState(depth===0);
  const [items,setItems]=useState<FileEntry[]>([]);
  const [error,setError]=useState('');
  const [over,setOver]=useState(false);
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const clear=()=>{if(timer.current!==null){clearTimeout(timer.current);timer.current=null;}setOver(false);};
  useEffect(()=>()=>{if(timer.current!==null)clearTimeout(timer.current);},[]);
  useEffect(()=>{if(!dragged.length)clear();},[dragged]);
  useEffect(()=>{if(!expanded)return;let cancelled=false;listProjectFiles(projectId,path).then(v=>{if(!cancelled){setItems(v.entries);setError('');}}).catch(e=>{if(!cancelled)setError(String(e));});return()=>{cancelled=true;};},[projectId,path,expanded,revision]);
  const valid=dragged.length>0&&dragged.every(p=>p!==path&&!path.startsWith(p+'/'))&&dragged.some(p=>p.split('/').slice(0,-1).join('/')!==path);
  const start=(e:React.DragEvent,p:string)=>{e.stopPropagation();e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',p);onDrag(p);};
  return <div>{depth>0&&<button draggable onDragStart={e=>start(e,path)} onDragEnd={()=>onDrag(null)} onDragOver={e=>{if(!valid)return;e.preventDefault();e.stopPropagation();e.dataTransfer.dropEffect='move';setOver(true);if(!expanded&&timer.current===null)timer.current=setTimeout(()=>setExpanded(true),650);}} onDragLeave={clear} onDrop={e=>{e.preventDefault();e.stopPropagation();clear();if(valid){setExpanded(true);onMove(dragged,path);}onDrag(null);}} data-entry-kind="directory" data-entry-path={path} aria-pressed={selection.includes(path)} className={`ide-tree-row ${selection.includes(path)?'ide-tree-selected':''} ${over?'ide-drop-target':''}`} style={{paddingLeft:depth*13}} onContextMenu={e=>onMenu(e,path)} onClick={e=>{if(onSelect(e,path))setExpanded(v=>!v);}}>{expanded?<ChevronDown size={13}/>:<ChevronRight size={13}/>}<Folder size={14}/>{path.split('/').pop()}</button>}{expanded&&<>{error&&<small className="ide-error">{error}</small>}{items.map(item=>item.kind==='directory'?<FolderTree key={item.path} {...{projectId,onOpen,revision,onMenu,dragged,onDrag,onMove,selection,onSelect}} path={item.path} depth={depth+1}/>:<button draggable onDragStart={e=>start(e,item.path)} onDragEnd={()=>onDrag(null)} key={item.path} data-entry-kind="file" data-entry-path={item.path} aria-pressed={selection.includes(item.path)} className={`ide-tree-row ${selection.includes(item.path)?'ide-tree-selected':''}`} style={{paddingLeft:(depth+1)*13+13}} title={item.path} onContextMenu={e=>onMenu(e,item.path,true)} onClick={e=>{if(onSelect(e,item.path))onOpen(item.path);}}><FileCode size={14}/>{item.name}</button>)}</>}</div>;
}
export default function IDEWorkspace({project,approved,digest,onApprove,onProjectUpdated,onDirtyChange}:Props){
  const [resource,setResource]=useState<ResourceTarget|null>(null);
  const [languageBusy,setLanguageBusy]=useState(false);
  async function changeProjectLanguage(value: ProjectLanguage) {
    if (languageBusy || value === project.language) return;
    setLanguageBusy(true);
    try { onProjectUpdated(await updateProjectLanguage(project.id,value)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLanguageBusy(false); }
  }
  const [tabs,setTabs]=useState<Tab[]>([]);
  useEffect(()=>{onDirtyChange(tabs.some(t=>t.dirty));},[tabs,onDirtyChange]);
  const [active,setActive]=useState<string|null>(null);
  const [excluded,setExcluded]=useState<string[]>([]);
  const addContext=(path:string)=>{setExcluded(old=>old.filter(p=>p!==path));onApprove([...new Set([...approved,path])].slice(0,8),null);setAssistantVisible(true);};
  const [revision,setRevision]=useState(0);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const [authorized,setAuthorized]=useState(false);
  const [createName,setCreateName]=useState('');
  const [creating,setCreating]=useState<'file'|'folder'|false>(false);
  const [createMenu,setCreateMenu]=useState(false);
  const [dragged,setDragged]=useState<string[]>([]);
  const [selection,setSelection]=useState<string[]>([]);
  const [clipboard,setClipboard]=useState<string[]>([]);
  const anchor=useRef<string|null>(null);
  const treeRef=useRef<HTMLDivElement>(null);
  function selectEntry(e:React.MouseEvent,path:string){
    if(e.shiftKey){const visible=Array.from(treeRef.current?.querySelectorAll<HTMLElement>('[data-entry-path]')??[]).map(el=>el.dataset.entryPath!);const a=visible.indexOf(anchor.current??path), b=visible.indexOf(path);setSelection(a<0?[path]:visible.slice(Math.min(a,b),Math.max(a,b)+1));return false;}
    anchor.current=path;
    if(e.ctrlKey||e.metaKey){setSelection(old=>old.includes(path)?old.filter(p=>p!==path):[...old,path]);return false;}
    setSelection([path]);return true;
  }
  const topPaths=(paths:string[])=>paths.filter(p=>!paths.some(q=>q!==p&&p.startsWith(q+'/')));

  function copySelection(paths:string[]){
    setClipboard(topPaths(paths));setMessage(`Copied ${topPaths(paths).length} items`);
  }
  async function paste(parent:string){
    if(busy||!clipboard.length)return;
    if(tabsRef.current.some(t=>t.dirty&&clipboard.some(p=>t.path===p||t.path.startsWith(p+'/')))){setError('Save copied files before pasting');return;}
    setBusy(true);setError('');
    try{const result=await copyEntries(project.id,clipboard,parent,authorized);setRevision(n=>n+1);setReview(null);setMessage(`Copied ${result.completed.length} items`);if(result.error)setError(result.error);}
    catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}
  }
  function rootMenu(e:React.MouseEvent){e.preventDefault();setSelection([]);anchor.current=null;setResource({name:project.name,x:e.clientX,y:e.clientY,removeLabel:'',warning:'',newFolder:()=>beginCreate('folder'),paste:clipboard.length?()=>void paste(''):undefined});}
  function explorerKeys(e:React.KeyboardEvent){
    if(!(e.ctrlKey||e.metaKey)||busy)return;
    const key=e.key.toLowerCase();
    if(key==='c'&&selection.length){e.preventDefault();copySelection(selection);}
    if(key==='v'&&clipboard.length){e.preventDefault();const row=(e.target as HTMLElement).closest<HTMLElement>('[data-entry-path]');const path=row?.dataset.entryPath??'';void paste(row?.dataset.entryKind==='file'?path.split('/').slice(0,-1).join('/'):path);}
  }

  const [rootOver,setRootOver]=useState(false);
  const beginCreate=(kind:'file'|'folder',parent='')=>{setCreateName(parent?parent+'/':'');setCreating(kind);setCreateMenu(false);};
  async function submitCreate(){if(creating==='file'){newFile();return;}const path=createName.trim();if(!path||busy)return;setBusy(true);try{await createDirectory(project.id,path,authorized);setCreating(false);setCreateName('');setRevision(n=>n+1);setError('');}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
  async function changeEntries(paths:string[],parent:string|null){
    if(busy)throw new Error('Wait for the current editor operation');
    paths=topPaths(paths);
    const affected=(p:string)=>paths.some(q=>p===q||p.startsWith(q+'/'));
    if(parent===null&&tabsRef.current.some(t=>affected(t.path)&&t.dirty))throw new Error('Save or close unsaved files first');
    if(parent!==null&&paths.some(p=>{const dest=(parent?parent+'/':'')+p.split('/').pop();return tabsRef.current.some(t=>!affected(t.path)&&(t.path===dest||t.path.startsWith(dest+'/')));}))throw new Error('Destination has an open editor tab');
    setBusy(true);setError('');
    try{
      const result=await batchEntries(project.id,paths,parent,authorized);
      const match=(p:string)=>result.completed.find(c=>p===c.source||p.startsWith(c.source+'/'));
      const next=(p:string)=>{const c=match(p);return c?c.path+p.slice(c.source.length):p;};
      const keep=(p:string)=>parent!==null||!match(p);
      setTabs(old=>old.filter(t=>keep(t.path)).map(t=>({...t,path:next(t.path)})));
      setActive(old=>old&&keep(old)?next(old):null);
      setExcluded(old=>old.filter(keep).map(next));onApprove(approved.filter(keep).map(next),null);
      setSelection(old=>old.filter(keep).map(next));anchor.current=null;
      setReview(null);setRevision(n=>n+1);setMessage(`${parent===null?'Deleted':'Moved'} ${result.completed.length} items`);
      if(result.error)throw new Error(`${result.completed.length} items completed: ${result.error}`);
    }finally{setBusy(false);}
  }
  async function move(paths:string[],parent:string){try{await changeEntries(paths,parent);}catch(e){setError(e instanceof Error?e.message:String(e));}}
  function deleteSelection(paths:string[],x:number,y:number,direct=false){
    const items=topPaths(paths);setResource({copy:()=>copySelection(items),initialAction:direct?'delete':undefined,name:`${items.length} items`,x,y,removeLabel:`Delete ${items.length} items`,warning:`Permanently delete ${items.join(', ')}? Folder contents will also be deleted.`,remove:()=>changeEntries(items,null)});
  }
  const [bottom,setBottom]=useState(false);
  const [runRequest,setRunRequest]=useState<{path:string;id:number}|null>(null);
  const [terminalConnected,setTerminalConnected]=useState(false);
  function closeTerminal(){setBottom(false);setRunRequest(null);setTerminalConnected(false);}
  function runFile(path:string){setRunRequest(old=>({path,id:(old?.id??0)+1}));setBottom(true);setTerminalConnected(true);}
  const [explorerVisible,setExplorerVisible]=useState(true);
  const [assistantVisible,setAssistantVisible]=useState(true);
  const [explorerWidth,setExplorerWidth]=useState(225);
  const [assistantWidth,setAssistantWidth]=useState(355);
  const [terminalHeight,setTerminalHeight]=useState(240);
  const [review,setReview]=useState<{path:string;before:string;after:string}|null>(null);
  useEffect(()=>{setTabs([]);setActive(null);setReview(null);setAuthorized(false);setSelection([]);setDragged([]);setClipboard([]);anchor.current=null;},[project.id]);
  const tabsRef=useRef(tabs);tabsRef.current=tabs;
  const activeRef=useRef(active);activeRef.current=active;
  const selected=tabs.find(t=>t.path===active);
  const open=useCallback(async(path:string)=>{
    setReview(null);
    if(tabsRef.current.some(t=>t.path===path)){setActive(path);return;}
    try {const data=await openEditableFile(project.id,path);setTabs(prev=>[...prev,{...data,saved:data.content,dirty:false,isNew:false}]);setActive(path);setError('');}
    catch(e){setError(e instanceof Error?e.message:String(e));}
  },[project.id]);
  const save=useCallback(async(path:string)=>{
    const tab=tabsRef.current.find(t=>t.path===path);if(!tab)return;
    setBusy(true);setError('');
    try{const result=await saveEditableFile(project.id,path,tab.content,tab.sha256,tab.isNew,authorized);
      setTabs(prev=>prev.map(t=>t.path===path?{...t,sha256:result.sha256,saved:result.content,dirty:t.content!==result.content,isNew:false}:t));setRevision(n=>n+1);setMessage(`Saved ${path}`);
    }catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}
  },[project.id,authorized]);
  const saveRef=useRef(save);saveRef.current=save;
  useEffect(()=>{const handler=(e:KeyboardEvent)=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();if(activeRef.current)void saveRef.current(activeRef.current);}};window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);},[]);
  function close(path:string){const tab=tabsRef.current.find(t=>t.path===path);if(tab?.dirty&&!window.confirm(`Discard unsaved changes in ${path}?`))return;setTabs(prev=>prev.filter(t=>t.path!==path));if(active===path)setActive(tabsRef.current.filter(t=>t.path!==path).at(-1)?.path??null);}
  function newFile(){const path=createName.trim();if(!path)return;if(tabs.some(t=>t.path===path)){setError('File is already open');return;}setTabs(prev=>[...prev,{path,content:'',saved:'',sha256:null,dirty:true,isNew:true}]);setActive(path);setCreating(false);setCreateName('');}
  function entryMenu(e:React.MouseEvent,path:string,isFile=false){
    e.preventDefault();e.stopPropagation();
    if(selection.includes(path)&&selection.length>1){deleteSelection(selection,e.clientX,e.clientY);return;}
    setSelection([path]);anchor.current=path;
    const affected=(p:string)=>p===path||p.startsWith(path+'/');
    const check=()=>{if(busy)throw new Error('Wait for the current editor operation');if(project.read_only&&!authorized)throw new Error('Enable manual edits for this registered project first');if(tabsRef.current.some(t=>affected(t.path)&&t.dirty))throw new Error('Save or close unsaved files first');};
    const refresh=()=>{setReview(null);onApprove([],null);setRevision(n=>n+1);};
    setResource({copy:()=>copySelection([path]),paste:clipboard.length?()=>void paste(isFile?path.split('/').slice(0,-1).join('/'):path):undefined,newFolder:!isFile?()=>beginCreate('folder',path):undefined,addToChat:isFile?()=>addContext(path):undefined,name:path.split('/').pop()!,x:e.clientX,y:e.clientY,removeLabel:'Delete',warning:`Permanently delete ${path}? All contents of a folder will also be deleted.`,rename:async name=>{check();const result=await renameEntry(project.id,path,name,authorized);const next=(p:string)=>affected(p)?result.path+p.slice(path.length):p;setTabs(old=>old.map(t=>({...t,path:next(t.path)})));setActive(old=>old?next(old):null);setSelection(old=>old.map(next));anchor.current=null;refresh();},remove:async()=>{check();await changeEntries([path],null);}});
  }
  function startResize(event:React.PointerEvent<HTMLDivElement>, target:'explorer'|'assistant'|'terminal') {
    event.preventDefault();
    const x=event.clientX,y=event.clientY;
    const initial=target==='explorer'?explorerWidth:target==='assistant'?assistantWidth:terminalHeight;
    const move=(e:PointerEvent)=>{
      if(target==='explorer')setExplorerWidth(Math.max(150,Math.min(420,initial+e.clientX-x)));
      else if(target==='assistant')setAssistantWidth(Math.max(270,Math.min(650,initial+x-e.clientX)));
      else setTerminalHeight(Math.max(130,Math.min(520,initial+y-e.clientY)));
    };
    const end=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',end);};
    window.addEventListener('pointermove',move);window.addEventListener('pointerup',end);
  }
  async function reviewChange(proposalId:string,change:ProposalChange){
    try { const diff=await previewProposalFile(proposalId,change.path);setReview(diff);setError(''); }
    catch(e){setError(e instanceof Error?e.message:String(e));}
  }
  return <div className="ide-root ide-v32" style={{gridTemplateColumns:`${explorerVisible?`${explorerWidth}px 5px `:""}minmax(0,1fr)${assistantVisible?` 5px ${assistantWidth}px`:""}`}}>
    {explorerVisible&&<aside className="ide-explorer"><div className="ide-pane-title"><FolderOpen size={15}/> EXPLORER <button title="Refresh files" onClick={()=>setRevision(n=>n+1)}><RefreshCw size={14}/></button><button title="New resource" aria-expanded={createMenu} onClick={()=>setCreateMenu(v=>!v)}><Plus size={15}/></button></div>
      {createMenu&&<div className="ide-create-menu"><button onClick={()=>beginCreate('file')}><FilePlus size={14}/> New file</button><button onClick={()=>beginCreate('folder')}><FolderPlus size={14}/> New folder</button></div>}
      <div tabIndex={0} onClick={()=>{setSelection([]);anchor.current=null;}} onContextMenu={rootMenu} onKeyDown={explorerKeys} className={`ide-project-title ${rootOver?'ide-drop-target':''}`} onDragOver={e=>{if(dragged.some(p=>p.includes('/'))){e.preventDefault();e.dataTransfer.dropEffect='move';setRootOver(true);}}} onDragLeave={()=>setRootOver(false)} onDrop={e=>{e.preventDefault();setRootOver(false);if(dragged.some(p=>p.includes('/')))void move(dragged,'');setDragged([]);}}><ProjectLanguageIcon language={project.language} size={15}/>{project.name}</div>
      {creating&&<div className="ide-new-file"><input autoFocus placeholder={creating==='folder'?'New folder name':'src/new_file.py'} value={createName} onChange={e=>setCreateName(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')void submitCreate();if(e.key==='Escape')setCreating(false);}}/><button disabled={busy} onClick={()=>void submitCreate()}>Create {creating}</button></div>}
      <div className="ide-tree" ref={treeRef} onKeyDown={e=>{explorerKeys(e);if(e.key==='Escape'){setSelection([]);anchor.current=null;}if(e.key==='Delete'&&selection.length&&!busy){e.preventDefault();const rect=e.currentTarget.getBoundingClientRect();deleteSelection(selection,rect.left,rect.top,true);}}}><FolderTree projectId={project.id} onOpen={p=>void open(p)} revision={revision} onMenu={entryMenu} dragged={dragged} onDrag={p=>{setDragged(p?topPaths(selection.includes(p)?selection:[p]):[]);if(p&&!selection.includes(p))setSelection([p]);if(!p)setRootOver(false);}} selection={selection} onSelect={selectEntry} onMove={(p,d)=>void move(p,d)}/></div>
    </aside>}
    {explorerVisible&&<div className="ide-resize-handle" role="separator" aria-label="Resize explorer" onPointerDown={e=>startResize(e,"explorer")}/>}
    <section className="ide-center"><div className="ide-quickbar"><button title="Toggle explorer" onClick={()=>setExplorerVisible(v=>!v)}>{explorerVisible?<PanelLeftClose size={15}/>:<PanelLeftOpen size={15}/>}</button><span>{project.name}</span><div><button onClick={()=>bottom?closeTerminal():setBottom(true)}><TerminalSquare size={14}/> Terminal</button><button title="Toggle AI assistant" onClick={()=>setAssistantVisible(v=>!v)}>{assistantVisible?<PanelRightClose size={15}/>:<PanelRightOpen size={15}/>}</button></div></div><div className="ide-tabs">{review&&<div className="ide-tab ide-tab-active"><button onClick={()=>{}}><FileCode size={14}/>Review: {review.path}</button><button title="Close review" onClick={()=>setReview(null)}><X size={13}/></button></div>}{tabs.map(t=><div key={t.path} className={`ide-tab ${t.path===active?'ide-tab-active':''}`}><button onClick={()=>setActive(t.path)}><FileCode size={14}/>{t.path.split('/').pop()}{t.dirty?' ●':''}</button><button title="Close tab" onClick={()=>close(t.path)}><X size={13}/></button></div>)}</div>
      {review?<><div className="ide-editor-toolbar"><span>Review changes · {review.path} · Left: current file / Right: proposed</span><button onClick={()=>setReview(null)}>Close review</button></div><div className="ide-editor"><DiffEditor theme="vs-dark" language={language(review.path)} original={review.before} modified={review.after} options={{readOnly:true,renderSideBySide:true,automaticLayout:true,minimap:{enabled:false},scrollBeyondLastLine:false}}/></div></>:selected?<><div className="ide-editor-toolbar"><span>{selected.path}</span><div>{(/\.(py|java|kt)$/i.test(selected.path))&&<button title={terminalConnected?'Stop the current terminal before running':selected.dirty||selected.isNew?'Save the file before running':'Run file'} disabled={busy||selected.dirty||selected.isNew||terminalConnected} onClick={()=>runFile(selected.path)}><Play size={15} color="#4ade80"/> Run</button>}<button title="Save (Ctrl+S)" disabled={busy||!selected.dirty} onClick={()=>void save(selected.path)}><Save size={15}/> Save</button><button title="File actions" disabled={busy||selected.isNew} onClick={e=>entryMenu(e,selected.path,true)}><MoreHorizontal size={15}/></button></div></div>
        <div className="ide-editor"><Editor theme="vs-dark" path={selected.path} language={language(selected.path)} value={selected.content} options={{fontSize:13,minimap:{enabled:false},automaticLayout:true,scrollBeyondLastLine:false}} onChange={value=>setTabs(prev=>prev.map(t=>t.path===selected.path?{...t,content:value??'',dirty:(value??'')!==t.saved}:t))}/></div></>:<div className="ide-welcome"><FileCode size={36}/><h2>{project.name}</h2><p>Choose a file from Explorer, or create a new file to start editing.</p><p>Ctrl+S to save · AI assistant on the right</p></div>}
      {project.read_only&&<label className="ide-write-authorization"><input type="checkbox" checked={authorized} onChange={e=>setAuthorized(e.target.checked)}/> Allow manual edits to this registered project (writes directly to disk)</label>}
      {(error||message)&&<div className={`ide-notification ${error?'ide-error':''}`}>{error?<CircleAlert size={15}/>:<Save size={15}/>} {error||message}<button onClick={()=>{setError('');setMessage('');}}><X size={14}/></button></div>}
      {bottom&&<><div className="ide-resize-horizontal" role="separator" aria-label="Resize terminal" onPointerDown={e=>startResize(e,"terminal")}/><div className="ide-terminal-panel" style={{height:terminalHeight}}><div className="ide-terminal-header"><strong>TERMINAL</strong><button onClick={closeTerminal} title="Close terminal"><X size={14}/></button></div><TerminalPanel key={`${project.id}:${runRequest?.id??0}`} projectId={project.id} runPath={runRequest?.path} onConnectionChange={setTerminalConnected}/></div></>}
    </section>
    {assistantVisible&&<div className="ide-resize-handle" role="separator" aria-label="Resize AI panel" onPointerDown={e=>startResize(e,"assistant")}/>}
    {assistantVisible&&<aside className="ide-ai"><div className="ide-ai-header"><Bot size={17}/> AI Assistant</div>
      <div className="ide-ai-content"><AIChat projectId={project.id} projectName={project.name} projectKind={project.kind} contextPaths={approved} activePath={review||selected?.isNew?null:active} dirtyPaths={tabs.filter(t=>t.dirty).map(t=>t.path)} excluded={excluded} onExclude={path=>{setExcluded(old=>[...new Set([...old,path])]);onApprove(approved.filter(p=>p!==path),null);}} onAddContext={addContext} revision={revision} onReview={(id,change)=>void reviewChange(id,change)} onApplied={()=>setRevision(n=>n+1)}/></div>
    </aside>}
    {resource&&<ResourceActions target={resource} onClose={()=>setResource(null)}/>}
    <WorkspaceStatusBar key={project.id} project={project} revision={revision} busy={languageBusy} onLanguageChange={value=>void changeProjectLanguage(value)}/>
  </div>;
}
