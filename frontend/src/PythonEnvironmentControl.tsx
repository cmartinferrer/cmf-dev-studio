import { useEffect, useRef, useState } from 'react';
import { CheckCircle, ChevronUp, TerminalSquare } from 'lucide-react';
import { getPythonEnvironment, updatePythonEnvironment, type Project, type PythonEnvironment } from './api';

export default function PythonEnvironmentControl({ project, revision }: { project: Project; revision: number }) {
  const [info, setInfo] = useState<PythonEnvironment | null>(null);
  const [open, setOpen] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [path, setPath] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pending, setPending] = useState<'create' | 'select' | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    let active = true;
    getPythonEnvironment(project.id).then(value => { if (active) setInfo(value); }).catch(e => { if (active) setError(String(e.message ?? e)); });
    return () => { active = false; };
  }, [project.id, project.language, revision]);
  useEffect(() => {
    if (!open) return;
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) { setOpen(false); setPending(null); setAdvanced(false); }
    }
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  async function update(action: 'create' | 'select' | 'reset') {
    setBusy(true); setError(''); setPending(null);
    try {
      setInfo(await updatePythonEnvironment(project.id, action, action === 'select' ? path.trim() : undefined));
      setAdvanced(false); setPath('');
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  async function refresh() {
    setBusy(true); setError('');
    try { setInfo(await getPythonEnvironment(project.id)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  if (project.language === 'java' || project.language === 'kotlin' || (!info?.supported && project.language !== 'python')) return null;
  const label = info?.available ? `Python ${info.version ?? ''}${info.source === 'detected' ? ' (.venv)' : ''}` : 'Set up Python';
  const canCreate = !!info?.uv_available && !info.venv_exists;
  return <div ref={root} className="workspace-language-control" onKeyDown={e => { if (e.key === 'Escape') { setOpen(false); setPending(null); setAdvanced(false); trigger.current?.focus(); } }}>
    <button ref={trigger} type="button" className="workspace-language-trigger" aria-expanded={open} title={info?.path ?? label} onClick={() => { setOpen(v => !v); setPending(null); setAdvanced(false); }}><TerminalSquare size={14}/><span>{label}</span><ChevronUp size={12}/></button>
    {open && <div className="workspace-language-menu python-environment-menu" aria-label="Python environment">
      <div className="workspace-language-heading">Python environment</div>
      {info?.available ? <div className="python-environment-summary"><CheckCircle size={18}/><div><strong>Python {info.version ?? ''}</strong><small>{info.source === 'detected' ? 'Project environment' : 'Custom interpreter'}</small></div></div> : <div className="python-environment-summary"><div><strong>{info ? 'Set up Python' : 'Checking Python…'}</strong><small>{info?.venv_exists ? 'An environment exists but Python could not be detected.' : 'Create an isolated environment for this project.'}</small></div></div>}
      {info && !info.available && canCreate && !pending && <button type="button" className="python-environment-primary" disabled={busy} onClick={() => setPending('create')}>Create environment</button>}
      {info && !info.available && !info.uv_available && <small>Install uv on your computer to create an environment.</small>}
      {info?.source === 'selected' && !info.available && <button type="button" className="workspace-language-option" disabled={busy} onClick={() => void update('reset')}>Use project environment</button>}
      {pending && <div className="python-environment-confirm"><p>{pending === 'create' ? 'Create a Python environment in this project? No packages will be installed.' : 'Check the selected Python executable? Only continue if you trust it.'}</p><div className="python-environment-actions"><button type="button" className="python-environment-primary" disabled={busy} onClick={() => void update(pending)}>{pending === 'create' ? 'Create' : 'Continue'}</button><button type="button" className="python-environment-secondary" onClick={() => setPending(null)}>Cancel</button></div></div>}
      <button type="button" className="workspace-language-option" disabled={busy} onClick={() => { setAdvanced(v => !v); setPending(null); }} aria-expanded={advanced}>{advanced ? 'Hide advanced options' : 'Advanced options'}<ChevronUp size={12} style={{ marginLeft: 'auto', transform: advanced ? undefined : 'rotate(180deg)' }}/></button>
      {advanced && <div className="python-environment-advanced">
        {info?.path && <small className="python-environment-path">{info.path}</small>}
        <button type="button" className="workspace-language-option" disabled={busy} onClick={() => void refresh()}>Refresh detection</button>
        {info?.available && canCreate && <button type="button" className="workspace-language-option" disabled={busy} onClick={() => setPending('create')}>Create project environment</button>}
        {info?.source === 'selected' && info.available && <button type="button" className="workspace-language-option" disabled={busy} onClick={() => void update('reset')}>Use project environment</button>}
        <label className="python-environment-path">Custom Python executable<input value={path} disabled={busy} onChange={e => { setPath(e.target.value); setPending(null); }} placeholder="/usr/bin/python3"/></label>
        <button type="button" className="workspace-language-secondary" disabled={busy || !path.trim()} onClick={() => setPending('select')}>Use custom interpreter</button>
      </div>}
      {busy && <small role="status">Working…</small>}{error && <p className="ide-error" role="alert">{error}</p>}
      <small className="python-environment-note">Restart the terminal after changing Python. AI tests are not connected yet.</small>
    </div>}
  </div>;
}
