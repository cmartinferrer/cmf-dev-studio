import { useEffect, useRef, useState } from 'react';
import { Check, ChevronUp, FolderOpen } from 'lucide-react';
import { projectLanguageLabels, type Project, type ProjectLanguage } from './api';
import ProjectLanguageIcon from './ProjectLanguageIcon';
import PythonEnvironmentControl from './PythonEnvironmentControl';

/** Workspace metadata and language controls, independent of the editor panels. */
export default function WorkspaceStatusBar({ project, busy, onLanguageChange, revision }: {
  project: Project;
  busy: boolean;
  revision: number;
  onLanguageChange: (language: ProjectLanguage) => void;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const current = project.language ?? 'auto';
  useEffect(() => {
    if (!open) return;
    root.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus();
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  function close() { setOpen(false); trigger.current?.focus(); }
  return <footer className="workspace-status-bar" aria-label="Workspace status">
    <div className="workspace-status-left"><FolderOpen size={13}/><span>{project.kind === 'existing' ? 'Registered repository' : 'Managed workspace'}</span></div>
    <div className="workspace-status-right">
      <PythonEnvironmentControl project={project} revision={revision}/>
      <div className="workspace-language-control" ref={root} onBlur={event=>{if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);}} onKeyDown={event=>{
        if (event.key === 'Escape' && open) { event.preventDefault(); close(); }
        if (open && ['ArrowDown','ArrowUp','Home','End'].includes(event.key)) {
          event.preventDefault();
          const options = Array.from(root.current?.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]') ?? []);
          const index = options.indexOf(document.activeElement as HTMLButtonElement);
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length-1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
          options[next]?.focus();
        }
      }}>
        <button ref={trigger} type="button" className="workspace-language-trigger" aria-label={`Project language: ${projectLanguageLabels[current]}`} aria-haspopup="menu" aria-expanded={open} disabled={busy} onClick={()=>setOpen(value=>!value)}>
          <ProjectLanguageIcon language={current} size={14}/><span>{projectLanguageLabels[current]}</span><ChevronUp size={12}/>
        </button>
        {open && <div className="workspace-language-menu" role="menu" aria-label="Project language">
          <div className="workspace-language-heading" aria-hidden="true">Project language</div>
          {(Object.keys(projectLanguageLabels) as ProjectLanguage[]).map(value=><button type="button" key={value} role="menuitemradio" aria-checked={value===current} className="workspace-language-option" onClick={()=>{close(); if(value!==current) onLanguageChange(value);}}>
            <ProjectLanguageIcon language={value} size={18}/><span>{projectLanguageLabels[value]}</span>{value===current && <Check size={14} className="workspace-language-check"/>}
          </button>)}
        </div>}
      </div>
    </div>
  </footer>;
}
