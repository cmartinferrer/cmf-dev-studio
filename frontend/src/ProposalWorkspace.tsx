import { useEffect, useState } from 'react';
import { createProposal, getProposal, listProposals, type Proposal } from './api';

type Props = { projectId: string; contextPaths: string[]; contextDigest: string | null; projectKind: 'managed' | 'existing' };
export default function ProposalWorkspace({ projectId, contextPaths, contextDigest, projectKind }: Props) {
  const [task, setTask] = useState('');
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  useEffect(() => { setSelected(null); setProposals([]); setError(''); void listProposals(projectId).then(setProposals).catch(e => setError(String(e))); }, [projectId]);
  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    const refresh = async () => {
      try {
        const item = await getProposal(selected);
        if (cancelled) return;
        setProposals(old => [item, ...old.filter(p => p.id !== item.id)]);
      } catch (e) { if (!cancelled) setError(String(e)); }
    };
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 2000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [selected]);
  const current = proposals.find(p => p.id === selected) ?? proposals[0];
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const proposal = await createProposal(projectId, task, contextPaths, contextDigest);
      setProposals(old => [proposal, ...old]); setSelected(proposal.id); setTask(''); setExpanded(null);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return <section className="proposal-workspace">
    <div className="section-heading"><div><h2>Workspace proposals · v2.1</h2><p>Generate Python project files in an isolated snapshot. Review diffs; originals remain unchanged.</p></div></div>
    <div className="info-panel" style={{marginBottom: 20}}>
      <h3>{projectKind === 'managed' ? 'New Python project' : 'Existing Python repository'}</h3>
      <p style={{marginBottom: 12}}>Approved reference files: {contextPaths.length ? contextPaths.join(', ') : 'none — only new files can be generated'}</p>
      <form onSubmit={e => void submit(e)}>
        <textarea aria-label="Proposal task" rows={4} style={{width: '100%', padding: 12, borderRadius: 8, marginBottom: 12}} placeholder={projectKind === 'managed' ? 'Create a FastAPI application with GET /health, pyproject.toml, README.md and pytest tests.' : 'Add a helper function and tests. Select and approve existing files in Repository Insights first if they must be modified.'} value={task} onChange={e => setTask(e.target.value)}/>
        <button className="primary" type="submit" disabled={busy || !task.trim()}>{busy ? 'Preparing…' : 'Generate proposal'}</button>
      </form>
    </div>
    {error && <div role="alert" className="alert">{error}</div>}
    {proposals.length > 0 && <div style={{display:'flex', gap:8, flexWrap:'wrap', marginBottom:16}}>{proposals.map(p => <button key={p.id} className={current?.id === p.id ? 'primary' : 'secondary'} onClick={() => { setSelected(p.id); setExpanded(null); }}>{p.task.slice(0,45)} · {p.status}</button>)}</div>}
    {current && <div className="info-panel">
      <h3>Proposal · {current.status}</h3>
      <p>{current.task}</p>
      {current.status === 'running' || current.status === 'queued' ? <p>Gemini is preparing file operations. This can take a minute…</p> : null}
      {current.error && <div role="alert" className="alert">{current.error}</div>}
      {current.changes.map(change => <div key={change.path} style={{marginTop: 16}}>
        <button className="secondary" onClick={() => setExpanded(expanded === change.path ? null : change.path)}>{change.action.toUpperCase()} · {change.path} · {change.size} bytes {expanded === change.path ? '▴' : '▾'}</button>
        {expanded === change.path && <pre style={{overflowX:'auto', maxHeight:480, padding:16, borderRadius:8, background:'#101827', color:'#e5e7eb', whiteSpace:'pre'}}>{change.diff || '(No text changes)'}</pre>}
      </div>)}
      {current.status === 'ready' && <p style={{marginTop:16}}>Review only: no changes have been applied to your project. Applying proposals and project-level tests are planned for v2.2/v2.3.</p>}
    </div>}
  </section>;
}
