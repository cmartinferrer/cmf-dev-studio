import { useCallback, useEffect, useRef, useState } from 'react';
import Editor, { loader } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';
import JsonWorker from 'monaco-editor/esm/vs/language/json/json.worker?worker';
import CssWorker from 'monaco-editor/esm/vs/language/css/css.worker?worker';
import HtmlWorker from 'monaco-editor/esm/vs/language/html/html.worker?worker';
import TsWorker from 'monaco-editor/esm/vs/language/typescript/ts.worker?worker';

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
import { deleteEditableFile, listProjectFiles, openEditableFile, saveEditableFile, type FileEntry, type Project } from './api';
import ProposalWorkspace from './ProposalWorkspace';
import RepositoryInsights from './RepositoryInsights';
import MissionWorkspace from './MissionWorkspace';

type Tab = { path: string; content: string; saved: string; sha256: string | null; dirty: boolean; isNew: boolean };
type Props = { project: Project; approved: string[]; digest: string | null; onApprove: (paths:string[],digest:string | null)=>void };
function language(path: string) { const ext=path.split('.').pop()?.toLowerCase(); return ({py:'python',ts:'typescript',tsx:'typescript',js:'javascript',jsx:'javascript',json:'json',md:'markdown',yaml:'yaml',yml:'yaml',toml:'ini',html:'html',css:'css'} as Record<string,string>)[ext||''] || 'plaintext'; }
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
  const [side,setSide]=useState<'assistant'|'context'|'missions'>('assistant');
  const [revision,setRevision]=useState(0);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const [authorized,setAuthorized]=useState(false);
  const [createName,setCreateName]=useState('');
  const [creating,setCreating]=useState(false);
  const [bottom,setBottom]=useState(false);
  const tabsRef=useRef(tabs);tabsRef.current=tabs;
  const activeRef=useRef(active);activeRef.current=active;
  const selected=tabs.find(t=>t.path===active);
  const open=useCallback(async(path:string)=>{
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
  return <div className="ide-root">
    <aside className="ide-explorer"><div className="ide-pane-title"><FolderOpen size={15}/> EXPLORER <button title="Refresh files" onClick={()=>setRevision(n=>n+1)}><RefreshCw size={14}/></button><button title="New file" onClick={()=>setCreating(v=>!v)}><Plus size={15}/></button></div>
      <div className="ide-project-title">{project.name}</div>
      {creating&&<div className="ide-new-file"><input autoFocus placeholder="src/new_file.py" value={createName} onChange={e=>setCreateName(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')newFile();if(e.key==='Escape')setCreating(false);}}/><button onClick={newFile}>Create</button></div>}
      <div className="ide-tree"><FolderTree projectId={project.id} onOpen={p=>void open(p)} revision={revision}/></div>
      <div className="ide-explorer-bottom"><GitBranch size={14}/>{project.kind==='existing'?'Registered repository':'Managed workspace'}</div>
    </aside>
    <section className="ide-center"><div className="ide-tabs">{tabs.map(t=><div key={t.path} className={`ide-tab ${t.path===active?'ide-tab-active':''}`}><button onClick={()=>setActive(t.path)}><FileCode size={14}/>{t.path.split('/').pop()}{t.dirty?' ●':''}</button><button title="Close tab" onClick={()=>close(t.path)}><X size={13}/></button></div>)}</div>
      {selected?<><div className="ide-editor-toolbar"><span>{selected.path}</span><div><button title="Save (Ctrl+S)" disabled={busy||!selected.dirty} onClick={()=>void save(selected.path)}><Save size={15}/> Save</button><button title="Delete file" disabled={busy||selected.isNew} onClick={()=>void remove()}><Trash2 size={15}/></button></div></div>
        <div className="ide-editor"><Editor theme="vs-dark" path={selected.path} language={language(selected.path)} value={selected.content} options={{fontSize:13,minimap:{enabled:false},automaticLayout:true,scrollBeyondLastLine:false}} onChange={value=>setTabs(prev=>prev.map(t=>t.path===selected.path?{...t,content:value??'',dirty:(value??'')!==t.saved}:t))}/></div></>:<div className="ide-welcome"><FileCode size={36}/><h2>{project.name}</h2><p>Choose a file from Explorer, or create a new file to start editing.</p><p>Ctrl+S to save · AI assistant on the right</p></div>}
      {project.read_only&&<label className="ide-write-authorization"><input type="checkbox" checked={authorized} onChange={e=>setAuthorized(e.target.checked)}/> Allow manual edits to this registered project (writes directly to disk)</label>}
      {(error||message)&&<div className={`ide-notification ${error?'ide-error':''}`}>{error?<CircleAlert size={15}/>:<Save size={15}/>} {error||message}<button onClick={()=>{setError('');setMessage('');}}><X size={14}/></button></div>}
      <div className="ide-bottom"><button onClick={()=>setBottom(v=>!v)}>{bottom?'▾':'▸'} OUTPUT & SHORTCUTS</button>{bottom&&<div className="ide-output">Files save directly to the local project after your action. AI proposals are isolated until you approve them. Use Ctrl+S to save. Terminal and Git commands arrive in v3.2.</div>}</div>
    </section>
    <aside className="ide-ai"><div className="ide-ai-header"><Bot size={17}/> AI TEAM <div className="ide-ai-switch"><button className={side==='assistant'?'on':''} onClick={()=>setSide('assistant')}>Build</button><button className={side==='context'?'on':''} onClick={()=>setSide('context')}>Context</button><button className={side==='missions'?'on':''} onClick={()=>setSide('missions')}>History</button></div></div>
      <div className="ide-ai-content">{side==='assistant'?<ProposalWorkspace projectId={project.id} projectKind={project.kind} contextPaths={approved} contextDigest={digest}/>:side==='context'?<RepositoryInsights projectId={project.id} approved={approved} onApprove={onApprove} onGoToMissions={()=>setSide('missions')} onGoToProposals={()=>setSide('assistant')}/>:<MissionWorkspace projectId={project.id} contextPaths={approved} contextDigest={digest}/>}</div>
    </aside>
  </div>;
}
