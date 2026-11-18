import ResourceActions, { type ResourceTarget } from './ResourceActions';
import { renameProject, removeProject, setProjectOpen, getProject, projectPresence } from './api';
import packageJson from "../package.json";
import ProjectLanguageIcon from './ProjectLanguageIcon';
import FolderPicker from './FolderPicker';
import IDEWorkspace from './IDEWorkspace';
import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Bot, CheckCircle2, Code2, FolderOpen, LayoutGrid, Plus, RefreshCw, Search, X } from 'lucide-react';
import { createProject, listProjects, registerProject, projectLanguageLabels, type ProjectLanguage, type Project } from './api';

type Mode = 'create' | 'register';
export default function App() {
  const dirtyRef=useRef(false);
  const [resource,setResource]=useState<ResourceTarget|null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [modal, setModal] = useState<Mode | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [approvedContext, setApprovedContext] = useState<string[]>([]);
  const [approvedDigest, setApprovedDigest] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [path, setPath] = useState('');
  const [language, setLanguage] = useState<ProjectLanguage>('python');
  const [description, setDescription] = useState('');
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
  const active = projects.find(project => project.id === selected) ?? null;
  async function refresh() {
    setLoading(true); setError('');
    try { const data = await listProjects(); setProjects(data); setSelected(current => current && data.some(p => p.id === current) ? current : null); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load projects'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    if (!selected) return;
    let socket: WebSocket | undefined;
    let stopped = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const connect = () => {
      if(stopped) return;
      socket = projectPresence(selected);
      socket.onclose = () => { if(!stopped) retry = setTimeout(connect, 1500); };
    };
    connect();
    const close = () => { stopped=true; clearTimeout(retry); socket?.close(); void setProjectOpen(selected,false).catch(()=>{}); };
    const reopen = () => { if(stopped){stopped=false;connect();} };
    window.addEventListener('pagehide', close);
    window.addEventListener('pageshow', reopen);
    return () => { stopped=true; clearTimeout(retry); socket?.close(); window.removeEventListener('pagehide',close); window.removeEventListener('pageshow',reopen); };
  }, [selected]);
  async function selectProject(id:string|null) {
    if(id!==selected&&dirtyRef.current&&!window.confirm("Discard unsaved changes and switch workspace?"))return;
    if(id!==selected){try{if(id){await setProjectOpen(id,true);const updated=await getProject(id);setProjects(old=>old.map(p=>p.id===id?updated:p));}if(selected)await setProjectOpen(selected,false);}catch(e){setError(String(e));return;}dirtyRef.current=false;setSelected(id);setApprovedContext([]);setApprovedDigest(null);}
  }
  function openModal(mode: Mode) { if(dirtyRef.current&&!window.confirm("Discard unsaved changes if a new project is opened?"))return;setModal(mode); setName(''); setPath(''); setDescription(''); setLanguage('python'); setFormError(''); }
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setFormError('');
    try {
      const project = modal === 'create' ? await createProject(name.trim(), description.trim(), language, path.trim()) : await registerProject(path.trim());
      setProjects(current => [project, ...current.filter(p => p.id !== project.id)]);
      await setProjectOpen(project.id,true);const updated=await getProject(project.id);setProjects(old=>old.map(p=>p.id===updated.id?updated:p));if(selected)await setProjectOpen(selected,false);dirtyRef.current=false;setSelected(project.id); setApprovedContext([]); setApprovedDigest(null); setModal(null);
    } catch (err) { setFormError(err instanceof Error ? err.message : 'Unable to save project'); }
    finally { setBusy(false); }
  }
  function projectMenu(e:React.MouseEvent,p:Project){
    e.preventDefault();e.stopPropagation();
    if(selected===p.id)return;
    const remove=async(fromDisk:boolean)=>{await removeProject(p.id,fromDisk);setProjects(old=>old.filter(item=>item.id!==p.id));};
    setResource({name:p.name,x:e.clientX,y:e.clientY,removeLabel:'Remove from Workspace',warning:`Remove ${p.name} from Studio? Its files will remain on disk.`,rename:async name=>{const updated=await renameProject(p.id,name);setProjects(old=>old.map(item=>item.id===p.id?updated:item));},remove:()=>remove(false),deleteFromDisk:()=>remove(true),diskWarning:`Permanently delete ${p.name} and all its files from ${p.path}? This cannot be undone.`});
  }
  const filtered = projects.filter(p => `${p.name} ${p.description} ${p.path}`.toLowerCase().includes(search.toLowerCase()));
  return <div className="app">
    <header className="topbar studio-topbar"><div className="studio-brand" title={`CMF Dev Studio v${packageJson.version}`}><Bot size={20} aria-hidden="true"/><span>CMF Dev Studio</span></div></header>
    <div className="studio-body">
      {!active&&<aside className="studio-rail" aria-label="Workspace navigation">
      <button className={!active?'rail-active':''} title="Overview" aria-label="Overview" onClick={()=>selectProject(null)}><LayoutGrid size={20}/></button>
      <div className="studio-version" title={`CMF Dev Studio v${packageJson.version}`}>v{packageJson.version}</div>
    </aside>}
      <main className="main">
      <div className={active ? "content ide-content" : "content"}>
      {error && <div role="alert" className="alert">{error} <button onClick={() => void refresh()}>Retry</button></div>}
      {!active ? <>
        <div className="hero"><div className="eyebrow"><span className="sparkle">✦</span> YOUR DEVELOPMENT WORKSPACE</div><h1>Build with a team<br/>of <span>AI agents.</span></h1><p>Turn ideas into working software. Create a project, bring your existing code, and build iteratively with an autonomous team.</p><div className="hero-actions"><button className="primary" onClick={() => openModal('create')}><Plus size={17}/> New project</button><button className="secondary" onClick={() => openModal('register')}><FolderOpen size={17}/> Open existing project</button></div><div className="hero-deco"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><Bot size={70}/></div></div>
        <div className="section-heading"><div><h2>Your projects</h2><p>Pick up where you left off, or start something new.</p></div><button className="icon-button" title="Refresh projects" aria-label="Refresh projects" onClick={()=>void refresh()}><RefreshCw size={17}/></button><div className="search-box"><Search size={16}/><input aria-label="Search projects" placeholder="Search projects..." value={search} onChange={e => setSearch(e.target.value)}/></div></div>
        {loading ? <div className="empty">Loading projects…</div> : filtered.length ? <div className="cards">{filtered.map(p => <button key={p.id} onContextMenu={e=>projectMenu(e,p)} className="project-card" onClick={()=>selectProject(p.id)}><div className="card-top"><span className={`file-icon managed`}><ProjectLanguageIcon language={p.language} size={22}/></span><span className="card-arrow"><ArrowRight size={18}/></span></div><strong>{p.name}</strong><p>{p.description || p.path}</p><div className="card-footer"><span className="type-tag">{projectLanguageLabels[p.language]}</span><span>{new Date(p.created_at).toLocaleDateString()}</span></div></button>)}</div> : <div className="empty"><FolderOpen size={28}/><strong>{search ? 'No matching projects' : 'No projects yet'}</strong><p>{search ? 'Try a different search.' : 'Create your first project or register an existing folder to get started.'}</p></div>}
        <div className="bottom-section"><div className="section-heading"><div><h2>Your agent team</h2><p>Available in each project workspace.</p></div><span className="soon">READY</span></div><div className="agent-grid"><div className="agent"><div className="agent-icon analyst"><Search size={20}/></div><div><strong>Analyst</strong><p>Breaks down requirements</p></div></div><div className="agent"><div className="agent-icon developer"><Code2 size={20}/></div><div><strong>Developer</strong><p>Writes and improves code</p></div></div><div className="agent"><div className="agent-icon tester"><CheckCircle2 size={20}/></div><div><strong>Tester</strong><p>Validates the solution</p></div></div></div></div>
      </> : <>
        <IDEWorkspace onOverview={()=>selectProject(null)} key={active.id} project={active} onDirtyChange={dirty=>{dirtyRef.current=dirty;}} onProjectUpdated={updated => setProjects(current => current.map(p => p.id === updated.id ? updated : p))} approved={approvedContext} digest={approvedDigest} onApprove={(paths, digest) => { setApprovedContext(paths); setApprovedDigest(digest); }} />
      </>}
      </div>
      </main>
    </div>
    {modal && <div className="overlay" onMouseDown={e => { if (e.target === e.currentTarget && !busy) setModal(null); }}><div className="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><div className="dialog-heading"><div><div className="eyebrow">CMF DEV STUDIO</div><h2 id="dialog-title">{modal === 'create' ? 'Create a project' : 'Open an existing project'}</h2><p>{modal === 'create' ? 'Create a project in a local directory.' : 'Select an existing project folder to open it in CMF Dev Studio.'}</p></div><button aria-label="Close" className="icon-button" onClick={() => setModal(null)} disabled={busy}><X size={19}/></button></div><form onSubmit={e => void submit(e)}>
    {<label>{modal === 'create' ? 'Location (parent directory)' : 'Project directory'} <span>*</span><div className="folder-path-field"><input required value={path} onChange={e => setPath(e.target.value)} placeholder="/home/user/workspace/my-project"/><button type="button" className="secondary" onClick={() => setPickerOpen(true)}><FolderOpen size={16}/> Browse…</button></div><small>{modal === 'create' ? `Project folder: ${path || "…"}/${name || "…"}` : ""}</small></label>}
    {modal === 'create' && <label>Programming language <span>*</span><select required value={language} onChange={e => setLanguage(e.target.value as ProjectLanguage)}>{(['python', 'java', 'kotlin'] as const).map(value => <option key={value} value={value}>{projectLanguageLabels[value]}</option>)}</select><small>Agents use this language for implementation and tests.</small></label>}
    {modal === 'create' && <><label>Project name <span>*</span><input required maxLength={80} value={name} onChange={e => setName(e.target.value)} placeholder="My awesome project"/></label>
    <label>Description <small>(optional)</small><textarea maxLength={2000} rows={3} value={description} onChange={e => setDescription(e.target.value)} placeholder="What are you building?"/></label></>}
    {modal === 'register' && path.trim() && <label>Project name <strong>{path.trim().replace(/[\\/]+$/, '').split(/[\\/]/).pop()}</strong></label>}
    {formError && <div className="form-error" role="alert">{formError}</div>}
    <div className="dialog-footer"><button type="button" className="secondary" onClick={() => setModal(null)} disabled={busy}>Cancel</button><button type="submit" className="primary" disabled={busy}>{busy ? 'Saving…' : modal === 'create' ? 'Create project' : 'Open project'} <ArrowRight size={16}/></button></div></form></div></div>}
    {resource&&<ResourceActions target={resource} onClose={()=>setResource(null)}/>}
    {pickerOpen && <FolderPicker onClose={() => setPickerOpen(false)} onSelect={selectedPath => { setPath(selectedPath); setPickerOpen(false); }}/>}
  </div>;
}
