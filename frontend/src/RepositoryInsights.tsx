import { useEffect, useState } from 'react';
import { getRepositoryInsights, previewRepositoryContext, type RepositoryInsights as Insights, type ContextPreview } from './api';

type Props = { projectId: string; approved: string[]; onApprove: (paths: string[], digest: string | null) => void; onGoToProposals: () => void };
export default function RepositoryInsights({ projectId, approved, onApprove, onGoToProposals }: Props) {
  const [insights, setInsights] = useState<Insights | null>(null);
  const [selected, setSelected] = useState<string[]>(approved);
  const [preview, setPreview] = useState<ContextPreview | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    setInsights(null); setSelected(approved); setPreview(null); setError(''); setLoading(true);
    getRepositoryInsights(projectId).then(data => { if (!cancelled) setInsights(data); })
      .catch(err => { if (!cancelled) setError(String(err)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [projectId]);
  function toggle(path: string) {
    setSelected(current => current.includes(path) ? current.filter(p => p !== path) : current.length < 8 ? [...current, path] : current);
    setPreview(null);
  }
  async function review() {
    setError('');
    try { setPreview(await previewRepositoryContext(projectId, selected)); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); setPreview(null); }
  }
  return <section className="insights-workspace">
    <div className="section-heading"><div><h2>Repository Insights</h2><p>Inspect the repository and explicitly approve source files before sending their contents to Gemini.</p></div></div>
    {loading && <p>Analyzing repository…</p>}
    {error && <div role="alert" className="alert">{error}</div>}
    {insights && <>
      <div className="insights-stats"><div><strong>Detected technologies</strong><p>{insights.technologies.join(' · ') || 'No known manifests detected'}</p></div><div><strong>Source extensions</strong><p>{Object.entries(insights.languages).map(([ext, count]) => `${ext}: ${count}`).join(' · ') || 'None'}</p></div></div>
      <h3>Choose reference files ({selected.length}/{insights.candidates.length} available · max {insights.limits.max_files})</h3>
      <p className="mission-muted">Only approved files are sent to Gemini when you submit a task. Hidden and sensitive files are excluded; supported build manifests are selectable. Review their contents first; automatic secret detection is not a guarantee.</p>
      {insights.truncated && <p className="mission-muted">Inventory limit reached. Some files may not appear.</p>}
      <div className="insights-files">{insights.candidates.map(file => <label key={file.path}><input type="checkbox" checked={selected.includes(file.path)} disabled={!selected.includes(file.path) && selected.length >= 8} onChange={() => toggle(file.path)}/><span>{file.path}</span><small>{file.size} B</small></label>)}</div>
      <div className="insights-actions"><button className="secondary" disabled={!selected.length} onClick={() => void review()}>Review selected content</button>{preview && <button className="secondary" onClick={() => { onApprove(selected, preview.digest); onGoToProposals(); }}>Approve & go to proposals</button>}</div>
      {preview && <div className="insights-preview"><h3>Exact context to be shared ({preview.total_bytes} bytes)</h3>{preview.files.map(file => <details key={file.path} open><summary>{file.path}</summary><pre>{file.content}</pre></details>)}</div>}
      {approved.length > 0 && <p className="mission-muted">Approved: {approved.join(', ')}</p>}
    </>}
  </section>;
}
