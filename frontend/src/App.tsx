import FolderPicker from './FolderPicker';
import IDEWorkspace from './IDEWorkspace';
import { useEffect, useState } from 'react';
import { Activity, ArrowRight, Bot, CheckCircle2, ChevronDown, Code2, FileCode2, Folder, FolderOpen, GitBranch, LayoutGrid, Plus, RefreshCw, Search, ShieldCheck, Terminal, X } from 'lucide-react';
import { createProject, listProjects, registerProject, type Project } from './api';

type Mode = 'create' | 'register';
export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [modal, setModal] = useState<Mode | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [workspaceTab, setWorkspaceTab] = useState<'files' | 'insights' | 'missions' | 'proposals' | 'details'>('files');
  const [approvedContext, setApprovedContext] = useState<string[]>([]);
  const [approvedDigest, setApprovedDigest] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [path, setPath] = useState('');
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
  function openModal(mode: Mode) { setModal(mode); setName(''); setPath(''); setDescription(''); setFormError(''); }
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setFormError('');
    try {
      const project = modal === 'create' ? await createProject(name.trim(), description.trim()) : await registerProject(path.trim(), name.trim(), description.trim());
      setProjects(current => [project, ...current.filter(p => p.id !== project.id)]);
      setSelected(project.id); setWorkspaceTab('files'); setApprovedContext([]); setApprovedDigest(null); setModal(null);
    } catch (err) { setFormError(err instanceof Error ? err.message : 'Unable to save project'); }
    finally { setBusy(false); }
  }
  const filtered = projects.filter(p => `${p.name} ${p.description} ${p.path}`.toLowerCase().includes(search.toLowerCase()));
  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><Bot size={22}/></div><div><strong>Multi-Agent</strong><span>STUDIO <em>ALPHA</em></span></div></div>
      <div className="nav-label">WORKSPACE</div>
      <button className={`nav-item ${!active ? 'active' : ''}`} onClick={() => { setSelected(null); setWorkspaceTab('files'); setApprovedContext([]); setApprovedDigest(null); }}><LayoutGrid size={17}/> Overview</button>
      <div className="nav-label projects-label">PROJECTS <button aria-label="Add project" title="New project" onClick={() => openModal('create')}><Plus size={16}/></button></div>
      <div className="project-nav">{projects.map(p => <button key={p.id} className={`project-nav-item ${active?.id === p.id ? 'chosen' : ''}`} onClick={() => { setSelected(p.id); setWorkspaceTab('files'); setApprovedContext([]); setApprovedDigest(null); }}><Folder size={16}/><span>{p.name}</span>{active?.id === p.id && <span className="nav-dot"/>}</button>)}</div>
      <div className="sidebar-bottom"><div className="sidebar-note"><ShieldCheck size={17}/><div><strong>Local workspace</strong><span>Projects stay on your machine</span></div></div><div className="sidebar-version"><span className="online-dot"/> API connected via localhost <span>v0.1</span></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{active ? active.name : 'Overview'}</strong></div><div className="top-actions"><span className="local-label"><span className="online-dot"/> Local development</span><button className="icon-button" title="Refresh projects" aria-label="Refresh projects" onClick={() => void refresh()}><RefreshCw size={17}/></button><div className="avatar">MS</div></div></header>
      <div className={active ? "content ide-content" : "content"}>
      {error && <div role="alert" className="alert">{error} <button onClick={() => void refresh()}>Retry</button></div>}
      {!active ? <>
        <div className="hero"><div className="eyebrow"><span className="sparkle">✦</span> YOUR DEVELOPMENT WORKSPACE</div><h1>Build with a team<br/>of <span>AI agents.</span></h1><p>Turn ideas into working software. Create a project, bring your existing code, and build iteratively with an autonomous team.</p><div className="hero-actions"><button className="primary" onClick={() => openModal('create')}><Plus size={17}/> New project</button><button className="secondary" onClick={() => openModal('register')}><FolderOpen size={17}/> Open existing project</button></div><div className="hero-deco"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><Bot size={70}/></div></div>
        <div className="section-heading"><div><h2>Your projects</h2><p>Pick up where you left off, or start something new.</p></div><div className="search-box"><Search size={16}/><input aria-label="Search projects" placeholder="Search projects..." value={search} onChange={e => setSearch(e.target.value)}/></div></div>
        {loading ? <div className="empty">Loading projects…</div> : filtered.length ? <div className="cards">{filtered.map(p => <button key={p.id} className="project-card" onClick={() => { setSelected(p.id); setWorkspaceTab('files'); setApprovedContext([]); setApprovedDigest(null); }}><div className="card-top"><span className={`file-icon ${p.kind}`}><Folder size={22}/></span><span className="card-arrow"><ArrowRight size={18}/></span></div><strong>{p.name}</strong><p>{p.description || (p.kind === 'existing' ? 'Existing local project' : 'New managed project')}</p><div className="card-footer"><span className="type-tag">{p.kind === 'existing' ? 'Existing · Read only' : 'Managed'}</span><span>{new Date(p.created_at).toLocaleDateString()}</span></div></button>)}</div> : <div className="empty"><FolderOpen size={28}/><strong>{search ? 'No matching projects' : 'No projects yet'}</strong><p>{search ? 'Try a different search.' : 'Create your first project or register an existing folder to get started.'}</p></div>}
        <div className="bottom-section"><div className="section-heading"><div><h2>Your agent team</h2><p>Available in each project workspace.</p></div><span className="soon">READY</span></div><div className="agent-grid"><div className="agent"><div className="agent-icon analyst"><Search size={20}/></div><div><strong>Analyst</strong><p>Breaks down requirements</p></div></div><div className="agent"><div className="agent-icon developer"><Code2 size={20}/></div><div><strong>Developer</strong><p>Writes and improves code</p></div></div><div className="agent"><div className="agent-icon tester"><CheckCircle2 size={20}/></div><div><strong>Tester</strong><p>Validates the solution</p></div></div></div></div>
      </> : <>
        <IDEWorkspace key={active.id} project={active} approved={approvedContext} digest={approvedDigest} onApprove={(paths, digest) => { setApprovedContext(paths); setApprovedDigest(digest); }} />
      </>}
      </div>
    </main>
    {modal && <div className="overlay" onMouseDown={e => { if (e.target === e.currentTarget && !busy) setModal(null); }}><div className="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><div className="dialog-heading"><div><div className="eyebrow">MULTI-AGENT STUDIO</div><h2 id="dialog-title">{modal === 'create' ? 'Create a project' : 'Open an existing project'}</h2><p>{modal === 'create' ? 'Start with a new managed workspace.' : 'Register a folder on the backend machine without changing its files.'}</p></div><button aria-label="Close" className="icon-button" onClick={() => setModal(null)} disabled={busy}><X size={19}/></button></div><form onSubmit={e => void submit(e)}>
    {modal === 'register' && <label>Absolute directory path <span>*</span><div className="folder-path-field"><input required value={path} onChange={e => setPath(e.target.value)} placeholder="/home/user/workspace/my-project"/><button type="button" className="secondary" onClick={() => setPickerOpen(true)}><FolderOpen size={16}/> Browse…</button></div><small>This path must exist on the machine running FastAPI.</small></label>}
    <label>Project name {modal === 'create' && <span>*</span>}{modal === 'register' && <small>(optional)</small>}<input required={modal === 'create'} maxLength={80} value={name} onChange={e => setName(e.target.value)} placeholder={modal === 'create' ? 'My awesome project' : 'Use folder name by default'}/></label>
    <label>Description <small>(optional)</small><textarea maxLength={2000} rows={3} value={description} onChange={e => setDescription(e.target.value)} placeholder="What are you building?"/></label>
    {formError && <div className="form-error" role="alert">{formError}</div>}
    <div className="dialog-footer"><button type="button" className="secondary" onClick={() => setModal(null)} disabled={busy}>Cancel</button><button type="submit" className="primary" disabled={busy}>{busy ? 'Saving…' : modal === 'create' ? 'Create project' : 'Register project'} <ArrowRight size={16}/></button></div></form></div></div>}
    {pickerOpen && <FolderPicker onClose={() => setPickerOpen(false)} onSelect={selectedPath => { setPath(selectedPath); setPickerOpen(false); }}/>}
  </div>;
}
