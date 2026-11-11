import { useEffect, useState } from 'react';
import { Activity, CheckCircle2, CircleAlert, Code2, Play, RefreshCw, TestTube2 } from 'lucide-react';
import { getMission, listMissionEvents, listMissions, startMission, type MissionEvent, type MissionRun } from './api';

const activeStatus = (status: string) => status === 'queued' || status === 'running';
const formatTime = (value: string) => new Date(value).toLocaleString();

export default function MissionWorkspace({ projectId, contextPaths = [], contextDigest = null }: { projectId: string; contextPaths?: string[]; contextDigest?: string | null }) {
  const [runs, setRuns] = useState<MissionRun[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [run, setRun] = useState<MissionRun | null>(null);
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setRuns([]); setRun(null); setEvents([]); setSelectedId(null); setError(''); setLoading(true);
    listMissions(projectId).then(data => {
      if (cancelled) return;
      setRuns(data); setSelectedId(data[0]?.id ?? null);
    }).catch(err => { if (!cancelled) setError(String(err)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [projectId]);

  useEffect(() => {
    if (!selectedId) { setRun(null); setEvents([]); return; }
    let cancelled = false;
    setRun(null); setEvents([]);
    async function poll() {
      try {
        const [latest, history] = await Promise.all([getMission(selectedId!), listMissionEvents(selectedId!)]);
        if (cancelled) return;
        setRun(latest); setEvents(history);
        setRuns(current => current.map(item => item.id === latest.id ? latest : item));
        setError('');
      } catch (err) { if (!cancelled) setError(err instanceof Error ? err.message : String(err)); }
    }
    void poll();
    const timer = window.setInterval(() => { void poll(); }, 2500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [selectedId]);

  async function createMission(event: React.FormEvent) {
    event.preventDefault();
    if (!description.trim() || submitting) return;
    setSubmitting(true); setError('');
    try {
      const created = await startMission(projectId, description.trim(), contextPaths, contextDigest);
      setRuns(current => [created, ...current]);
      setSelectedId(created.id); setDescription('');
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setSubmitting(false); }
  }

  const running = runs.some(item => activeStatus(item.status));
  const result = run?.result;
  return <section className="missions-workspace">
    <div className="section-heading"><div><h2><Activity size={19}/> Agent missions</h2><p>Run tasks with Analyst, Developer and Tester. Generated code stays in mission history; project files are not modified.</p></div></div>
    <form className="mission-form" onSubmit={e => void createMission(e)}>
      <label htmlFor="mission-description">New mission</label>
      <p className="mission-muted">{contextPaths.length ? `Approved repository context: ${contextPaths.join(', ')}. These files will be sent to Gemini.` : 'No repository files approved. Mission runs without repository context.'}</p>
      <textarea id="mission-description" rows={3} maxLength={10000} value={description} onChange={e => setDescription(e.target.value)} placeholder="Describe what the agent team should implement and test…" required />
      <div className="mission-form-footer"><span>{running ? 'A mission is already active for this project.' : 'Execution uses Gemini and Docker; review generated output before using it.'}</span><button type="submit" className="primary" disabled={submitting || running || !description.trim()}><Play size={15}/>{submitting ? 'Starting…' : 'Run mission'}</button></div>
    </form>
    {error && <div role="alert" className="alert">{error}</div>}
    <div className="mission-columns">
      <div className="mission-list"><h3>Mission history</h3>{loading ? <p className="mission-muted">Loading…</p> : runs.length === 0 ? <p className="mission-muted">No missions yet.</p> : runs.map(item => <button type="button" key={item.id} className={`mission-list-item ${selectedId === item.id ? 'selected' : ''}`} onClick={() => setSelectedId(item.id)}><span className="mission-list-title">{item.description}</span><span className="mission-list-meta"><span className={`mission-status status-${item.status}`}>{item.status}</span>{formatTime(item.created_at)}</span></button>)}</div>
      <div className="mission-detail"><h3>Execution details {run && <span className={`mission-status status-${run.status}`}>{run.status}</span>}</h3>
        {!selectedId ? <p className="mission-muted">Select a mission to inspect its execution.</p> : !run ? <p className="mission-muted">Loading mission…</p> : <>
          <p className="mission-task">{run.description}</p>
          {activeStatus(run.status) && <p className="mission-muted"><RefreshCw size={14}/> Updating automatically every 2.5 seconds…</p>}
          {run.error && <div className="alert" role="alert"><CircleAlert size={15}/> {run.error}</div>}
          <h4>Timeline</h4>
          {events.length === 0 ? <p className="mission-muted">Waiting for events…</p> : <ol className="mission-events">{events.map(item => <li key={item.id}><span className="mission-event-icon">{item.type.endsWith('completed') || item.status === 'passed' ? <CheckCircle2 size={15}/> : item.type === 'test_started' ? <TestTube2 size={15}/> : <Activity size={15}/>}</span><div><strong>{item.type.replaceAll('_', ' ')}</strong> {item.agent && <span>· {item.agent}</span>} {item.attempt && <span>· attempt {item.attempt}{item.max_attempts ? `/${item.max_attempts}` : ''}</span>}{item.status && <span className={`mission-status status-${item.status}`}>{item.status}</span>}<small>{formatTime(item.occurred_at)}</small>{item.message && <details><summary>Test output / details</summary><pre>{item.message}</pre></details>}</div></li>)}</ol>}
          {result && <div className="mission-artifacts"><h4><Code2 size={16}/> Generated artifacts</h4><p className="mission-muted">{result.attempts} test attempt(s). These artifacts are stored in SQLite, not written into the selected project.</p>{result.code && <details open><summary>Python code</summary><pre>{result.code}</pre></details>}{result.tests && <details><summary>Generated tests</summary><pre>{result.tests}</pre></details>}{result.requirements && <details><summary>Requirements</summary><pre>{Array.isArray(result.requirements) ? result.requirements.join('\n') : result.requirements}</pre></details>}{result.feedback && <details><summary>Feedback</summary><pre>{result.feedback}</pre></details>}</div>}
        </>}
      </div>
    </div>
  </section>;
}
