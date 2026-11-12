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
import { Bot, ChevronDown, ChevronRight, CircleAlert, FileCode, Folder, FolderOpen, GitBranch, Plus, RefreshCw, Save, Trash2, X } from 'lucide-react';
import { deleteEditableFile, listProjectFiles, openEditableFile, saveEditableFile, previewProposalFile, type FileEntry, type Project, type ProposalChange } from './api';
import AIChat from './AIChat';
import RepositoryInsights from './RepositoryInsights';
import TerminalPanel from './TerminalPanel';
import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, TerminalSquare, SlidersHorizontal } from 'lucide-react';

type Tab = { path: string; content: string; saved: string; sha256: string | null; dirty: boolean; isNew: boolean };
type Props = { project: Project; approved: string[]; digest: string | null; onApprove: (paths:string[],digest:string | null)=>void };
function language(path: string) { const ext=path.split('.').pop()?.toLowerCase(); return ({py:'python',ts:'typescript',tsx:'typescript',js:'javascript',jsx:'javascript',json:'json',md:'markdown',yaml:'yaml',yml:'yaml',toml:'ini',java:'java',kt:'kotlin',kts:'kotlin',xml:'xml',gradle:'groovy',html:'html',css:'css'} as Record<string,string>)[ext||''] || 'plaintext'; }
function FolderTree({projectId, path='', depth=0, onOpen, revision}:{projectId:string;path?:string;depth?:number;onOpen:(path:string)=>void;revision:number}) {
  const [expanded,setExpanded]=useState(depth===0);
  const [items,setItems]=useState<FileEntry[]>([]);
  const [error,setError]=useState('');
  useEffect(()=>{if(!expanded)return;let cancelled=false;listProjectFiles(projectId,path).then(v=>{if(!cancelled){setItems(v.entries);setError('');}}).catch(e=>{if(!cancelled)setError(String(e));});return()=>{cancelled=true;};},[projectId,path,expanded,revision]);
  return <div>{depth>0&&<button className="ide-tree-row" style={{paddingLeft:depth*13}} onClick={()=>setExpanded(v=>!v)}>{expanded?<ChevronDown size={13}/>:<ChevronRight size={13}/>}<Folder size={14}/>{path.split('/').pop()}</button>}{expanded&&<>{error&&<small className="ide-error">{error}</small>}{items.map(item=>item.kind==='directory'?<FolderTree key={item.path} projectId={projectId} path={item.path} depth={depth+1} onOpen={onOpen} revision={revision}/>:<button key={item.path} className="ide-tree-row" style={{paddingLeft:(depth+1)*13+13}} title={item.path} onClick={()=>onOpen(item.path)}><FileCode size={14}/>{item.name}</button>)}</>}</div>;
}
export default function IDEWorkspace({project,approved,digest,onApprove}:Props){
  const [tabs,setTabs]=useState<Tab[]>([]);
  const [active,setActive]=useState<string|null>(null);
  const [side,setSide]=useState<'assistant'|'context'>('assistant');
  const [revision,setRevision]=useState(0);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const [authorized,setAuthorized]=useState(false);
  const [createName,setCreateName]=useState('');
  const [creating,setCreating]=useState(false);
  const [bottom,setBottom]=useState(false);
  const [explorerVisible,setExplorerVisible]=useState(true);
  const [assistantVisible,setAssistantVisible]=useState(true);
  const [explorerWidth,setExplorerWidth]=useState(225);
  const [assistantWidth,setAssistantWidth]=useState(355);
  const [terminalHeight,setTerminalHeight]=useState(240);
  const [showAdvanced,setShowAdvanced]=useState(false);
  const [review,setReview]=useState<{path:string;before:string;after:string}|null>(null);
  useEffect(()=>{setTabs([]);setActive(null);setReview(null);setAuthorized(false);},[project.id]);
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
  async function remove(){if(!selected||selected.isNew)return;if(!window.confirm(`Delete ${selected.path} permanently?`))return;setBusy(true);try{await deleteEditableFile(project.id,selected.path,selected.sha256!,authorized);setTabs(prev=>prev.filter(t=>t.path!==selected.path));setActive(null);setRevision(n=>n+1);setMessage(`Deleted ${selected.path}`);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
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
    {explorerVisible&&<aside className="ide-explorer"><div className="ide-pane-title"><FolderOpen size={15}/> EXPLORER <button title="Refresh files" onClick={()=>setRevision(n=>n+1)}><RefreshCw size={14}/></button><button title="New file" onClick={()=>setCreating(v=>!v)}><Plus size={15}/></button></div>
      <div className="ide-project-title">{project.name}</div>
      {creating&&<div className="ide-new-file"><input autoFocus placeholder="src/new_file.py" value={createName} onChange={e=>setCreateName(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')newFile();if(e.key==='Escape')setCreating(false);}}/><button onClick={newFile}>Create</button></div>}
      <div className="ide-tree"><FolderTree projectId={project.id} onOpen={p=>void open(p)} revision={revision}/></div>
      <div className="ide-explorer-bottom"><GitBranch size={14}/>{project.kind==='existing'?'Registered repository':'Managed workspace'}</div>
    </aside>}
    {explorerVisible&&<div className="ide-resize-handle" role="separator" aria-label="Resize explorer" onPointerDown={e=>startResize(e,"explorer")}/>}
    <section className="ide-center"><div className="ide-quickbar"><button title="Toggle explorer" onClick={()=>setExplorerVisible(v=>!v)}>{explorerVisible?<PanelLeftClose size={15}/>:<PanelLeftOpen size={15}/>}</button><span>{project.name}</span><div><button onClick={()=>setBottom(v=>!v)}><TerminalSquare size={14}/> Terminal</button><button title="Toggle AI assistant" onClick={()=>setAssistantVisible(v=>!v)}>{assistantVisible?<PanelRightClose size={15}/>:<PanelRightOpen size={15}/>}</button></div></div><div className="ide-tabs">{review&&<div className="ide-tab ide-tab-active"><button onClick={()=>{}}><FileCode size={14}/>Review: {review.path}</button><button title="Close review" onClick={()=>setReview(null)}><X size={13}/></button></div>}{tabs.map(t=><div key={t.path} className={`ide-tab ${t.path===active?'ide-tab-active':''}`}><button onClick={()=>setActive(t.path)}><FileCode size={14}/>{t.path.split('/').pop()}{t.dirty?' ●':''}</button><button title="Close tab" onClick={()=>close(t.path)}><X size={13}/></button></div>)}</div>
      {review?<><div className="ide-editor-toolbar"><span>Review changes · {review.path} · Left: current file / Right: proposed</span><button onClick={()=>setReview(null)}>Close review</button></div><div className="ide-editor"><DiffEditor theme="vs-dark" language={language(review.path)} original={review.before} modified={review.after} options={{readOnly:true,renderSideBySide:true,automaticLayout:true,minimap:{enabled:false},scrollBeyondLastLine:false}}/></div></>:selected?<><div className="ide-editor-toolbar"><span>{selected.path}</span><div><button title="Save (Ctrl+S)" disabled={busy||!selected.dirty} onClick={()=>void save(selected.path)}><Save size={15}/> Save</button><button title="Delete file" disabled={busy||selected.isNew} onClick={()=>void remove()}><Trash2 size={15}/></button></div></div>
        <div className="ide-editor"><Editor theme="vs-dark" path={selected.path} language={language(selected.path)} value={selected.content} options={{fontSize:13,minimap:{enabled:false},automaticLayout:true,scrollBeyondLastLine:false}} onChange={value=>setTabs(prev=>prev.map(t=>t.path===selected.path?{...t,content:value??'',dirty:(value??'')!==t.saved}:t))}/></div></>:<div className="ide-welcome"><FileCode size={36}/><h2>{project.name}</h2><p>Choose a file from Explorer, or create a new file to start editing.</p><p>Ctrl+S to save · AI assistant on the right</p></div>}
      {project.read_only&&<label className="ide-write-authorization"><input type="checkbox" checked={authorized} onChange={e=>setAuthorized(e.target.checked)}/> Allow manual edits to this registered project (writes directly to disk)</label>}
      {(error||message)&&<div className={`ide-notification ${error?'ide-error':''}`}>{error?<CircleAlert size={15}/>:<Save size={15}/>} {error||message}<button onClick={()=>{setError('');setMessage('');}}><X size={14}/></button></div>}
      {bottom&&<><div className="ide-resize-horizontal" role="separator" aria-label="Resize terminal" onPointerDown={e=>startResize(e,"terminal")}/><div className="ide-terminal-panel" style={{height:terminalHeight}}><div className="ide-terminal-header"><strong>TERMINAL</strong><button onClick={()=>setBottom(false)} title="Close terminal"><X size={14}/></button></div><TerminalPanel key={project.id} projectId={project.id}/></div></>}
    </section>
    {assistantVisible&&<div className="ide-resize-handle" role="separator" aria-label="Resize AI panel" onPointerDown={e=>startResize(e,"assistant")}/>}
    {assistantVisible&&<aside className="ide-ai"><div className="ide-ai-header"><Bot size={17}/> AI Assistant <button className="ide-advanced-toggle" onClick={()=>setShowAdvanced(v=>!v)} title="More AI tools"><SlidersHorizontal size={14}/></button></div>{showAdvanced&&<div className="ide-ai-switch ide-ai-switch-v32"><button className={side==='assistant'?'on':''} onClick={()=>setSide('assistant')}>Assistant</button><button className={side==='context'?'on':''} onClick={()=>setSide('context')}>Context</button></div>}
      <div className="ide-ai-content">{side==='assistant'?<AIChat projectId={project.id} projectName={project.name} projectKind={project.kind} contextPaths={approved} contextDigest={digest} onReview={(id,change)=>void reviewChange(id,change)} onApplied={()=>setRevision(n=>n+1)} onContext={()=>{setSide('context');setShowAdvanced(true);}} onApproveContext={onApprove}/>:<RepositoryInsights projectId={project.id} approved={approved} onApprove={onApprove} onGoToProposals={()=>setSide('assistant')}/>}</div>
    </aside>}
  </div>;
}
