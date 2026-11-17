import { useEffect, useRef, useState } from 'react';
import { Check, CheckCircle, ChevronUp, Coffee } from 'lucide-react';
import { getJdk, updateJdk, type JdkEnvironment, type Project } from './api';

export default function JdkEnvironmentControl({ project, revision }: { project: Project; revision: number }) {
  const [info, setInfo] = useState<JdkEnvironment | null>(null);
  const [open, setOpen] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [path, setPath] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    let active = true;
    getJdk(project.id).then(value => { if (active) setInfo(value); }).catch(e => { if (active) setError(String(e.message ?? e)); });
    return () => { active = false; };
  }, [project.id, project.language, revision]);
  useEffect(() => {
    if (!open) return;
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  async function change(home?: string | null) {
    setBusy(true); setError('');
    try { setInfo(await (home === undefined ? getJdk(project.id) : updateJdk(project.id, home))); setPath(''); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  if (project.language === 'python' || (!info?.supported && project.language === 'auto')) return null;
  const label = info?.current ? `JDK ${info.current.version}` : 'Set up Java';
  return <div ref={root} className="workspace-language-control" onKeyDown={e => { if (e.key === 'Escape') { setOpen(false); trigger.current?.focus(); } }}>
    <button ref={trigger} type="button" className="workspace-language-trigger" aria-expanded={open} title={info?.current?.path ?? label} onClick={() => setOpen(v => !v)}><Coffee size={14}/><span>{label}</span><ChevronUp size={12}/></button>
    {open && <div className="workspace-language-menu python-environment-menu" aria-label="Java environment">
      <div className="workspace-language-heading">Java environment</div>
      <div className="python-environment-summary">{info?.current && <CheckCircle size={18}/>}<div><strong>{info?.current ? `Java ${info.current.version}` : info ? 'Set up Java' : 'Checking Java…'}</strong><small>{info?.current ? 'Project JDK' : 'Install a JDK on your computer or select an existing one.'}</small></div></div>
      {!!info?.available.length && <div className="workspace-language-heading">Available JDKs</div>}
      {info?.available.map(jdk => <button key={jdk.path} type="button" title={jdk.path} className="workspace-language-option" disabled={busy} onClick={() => void change(jdk.path)}><span>Java {jdk.version}</span>{info.current?.path === jdk.path && <Check size={14} className="workspace-language-check"/>}</button>)}
      <button type="button" className="workspace-language-option" aria-expanded={advanced} onClick={() => setAdvanced(v => !v)}>Advanced options<ChevronUp size={12} style={{marginLeft:'auto', transform:advanced ? undefined : 'rotate(180deg)'}}/></button>
      {advanced && <div className="python-environment-advanced">
        {info?.current && <small className="python-environment-path">{info.current.path}</small>}
        <button type="button" className="workspace-language-option" disabled={busy} onClick={() => void change()}>Refresh detection</button>
        {info?.source === 'selected' && <button type="button" className="workspace-language-option" disabled={busy} onClick={() => void change(null)}>Use system JDK</button>}
        <label className="python-environment-path">Custom JDK directory<input value={path} onChange={e => setPath(e.target.value)} placeholder="/usr/lib/jvm/java-21-openjdk"/></label>
        <button type="button" className="python-environment-secondary" disabled={busy || !path.trim()} onClick={() => void change(path.trim())}>Use JDK</button>
      </div>}
      {busy && <small role="status">Working…</small>}{error && <p className="ide-error" role="alert">{error}</p>}
      <small className="python-environment-note">Selection is saved for this project. Terminal and AI tests are not changed yet.</small>
    </div>}
  </div>;
}
