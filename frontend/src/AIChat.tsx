import { useEffect, useRef, useState } from 'react';
import { Bot, Check, ChevronRight, CircleAlert, FileCode2, LoaderCircle, Paperclip, Send, Terminal, X } from 'lucide-react';
import { repairProposal, deferProposal, applyProposal, createProposal, getProposal, listProposals, testProposal, previewTest, type TestPreview, getRepositoryInsights, previewRepositoryContext, type RepositoryInsights, type ContextPreview, type Proposal, type ProposalChange } from './api';

type Props = { projectId: string; projectName: string; projectKind: 'managed'|'existing'; contextPaths: string[]; contextDigest: string|null; onReview: (proposalId:string, change: ProposalChange)=>void; onApplied: ()=>void; onContext: ()=>void; onApproveContext: (paths:string[], digest:string|null)=>void };
const activeStatuses = ['queued','running'];
const describe = (status: Proposal['status']) => ({queued:'Waiting for the AI…',running:'Preparing changes…',ready:'Changes ready · Approval required',tested:'Tests passed · Ready to review',test_failed:'Tests failed · Review the output',applied:'Changes applied',failed:'Could not prepare changes'})[status];

const needsContext = (error?: string | null) => /Permission required to read and modify|already exists: use modify|Review and approve repository context/i.test(error ?? '');


const commandText = (args:string[]) => args.map(arg=>/^[\w./:=+-]+$/.test(arg)?arg:JSON.stringify(arg)).join(' ');
const translator = (task:string) => {
  const es = /\b(crea(?:me)?|haz|anade|quiero|puedes|calculadora|modifica|corrige|implementa|por favor|necesito|genera|agrega|elimina|cambia|actualiza|pruebas|ficheros)\b/i.test(task.normalize('NFD').replace(/\p{M}/gu,''));
  return (en:string,spanish:string) => es?spanish:en;
};
function Conversation({item,projectName,onReview}:{item:Proposal;projectName:string;onReview:Props['onReview']}) {
  // Use persisted facts, not additional model calls or invented explanations.
  const t = translator(item.task);
  const events = (item.events ?? []).filter(e=>!['requested','agent_stage'].includes(e.kind));
  const generated = events.filter(e=>['files_generated','repair_ready'].includes(e.kind));
  const lastGenerated = generated[generated.length-1]?.sequence;
  const assistant = (children:React.ReactNode) => <div className="chat-dialog-assistant"><div className="chat-dialog-author"><Bot size={14}/> {t('Assistant','Asistente')}</div>{children}</div>;
  const user = (label:string) => <div className="chat-user-bubble chat-dialog-decision">{label}</div>;
  const files = <div className="chat-change-card"><div className="chat-change-summary"><strong>{item.changes.length} {t('files','ficheros')}</strong><span>{t('Review in editor','Revisar en el editor')}</span></div>{item.changes.map(change=><button key={change.path} className="chat-change-row" onClick={()=>onReview(item.id,change)}><FileCode2 size={14}/><span>{change.path}</span><small>{change.action}</small><ChevronRight size={13}/></button>)}</div>;
  const output = (value?:string) => value&&<details className="chat-history-detail"><summary>{t('Show output','Ver resultado')}</summary><pre className="chat-test-output">{value}</pre></details>;
  return <div className="chat-dialog">
    {events.map(event=>{const d=event.details;let content:React.ReactNode;
      switch(event.kind){
        case 'files_generated': case 'repair_ready': content=assistant(<><p>{event.kind==='repair_ready'?t('I have prepared a revised proposal.','He preparado una propuesta corregida.'):t(`I have prepared ${d.count ?? item.changes.length} files for your request.`,`He preparado ${d.count ?? item.changes.length} ficheros para tu petición.`)}</p>{event.sequence===lastGenerated&&files}</>);break;
        case 'command_approved': content=<>{assistant(<><p>{t('May I run this command to check the changes?','¿Puedo ejecutar este comando para comprobar los cambios?')}</p>{d.command&&<pre className="chat-history-command">{commandText(d.command)}</pre>}</>)}{user(t('Allow once','Permitir una vez'))}</>;break;
        case 'tests_skipped': content=<>{assistant(<p>{t('May I run the tests?','¿Puedo ejecutar los tests?')}</p>)}{user(t('Skip','Omitir'))}{assistant(<p>{t('I will leave the proposal pending.','Dejo la propuesta pendiente.')}</p>)}</>;break;
        case 'tests_passed': content=assistant(<><p>{t('The tests passed successfully.','Los tests han pasado correctamente.')}</p>{output(d.output)}</>);break;
        case 'tests_failed': content=assistant(<><p>{t('The test command failed. The project has not been changed.','La ejecución de los tests ha fallado. No he modificado el proyecto.')}</p>{output(d.output)}</>);break;
        case 'repair_requested': content=<>{assistant(<p>{t('Would you like me to try to fix the failure?','¿Quieres que intente corregir el fallo?')}</p>)}{user(t('Fix and retry','Corregir y reintentar'))}</>;break;
        case 'apply_deferred': content=<>{assistant(<p>{t(`May I apply the changes to ${projectName}?`,`¿Aplico los cambios a ${projectName}?`)}</p>)}{user(t('Not now','Ahora no'))}</>;break;
        case 'changes_applied': content=<>{assistant(<p>{t(`May I apply the changes to ${projectName}?`,`¿Aplico los cambios a ${projectName}?`)}</p>)}{user(t('Accept changes','Aceptar cambios'))}{assistant(<p>{t(`I have saved ${d.count ?? item.changes.length} files to your project.`,`He guardado ${d.count ?? item.changes.length} ficheros en tu proyecto.`)}</p>)}</>;break;
        case 'generation_failed': case 'repair_failed': content=assistant(<><p>{t('I could not prepare the changes.','No he podido preparar los cambios.')}</p>{output(d.error)}</>);break;
        default:return null;
      }return <div className="chat-dialog-turn" key={event.sequence}>{content}</div>;
    })}
    {!generated.length&&item.changes.length>0&&assistant(files)}
    {!events.some(e=>e.kind==='tests_passed'||e.kind==='tests_failed')&&item.test_output&&assistant(<><p>{item.status==='test_failed'?t('The tests failed.','Los tests han fallado.'):t('Test result','Resultado de los tests')}</p>{output(item.test_output)}</>)}
    {item.status==='applied'&&!events.some(e=>e.kind==='changes_applied')&&assistant(<p>{t('The changes are saved.','Los cambios están guardados.')}</p>)}
    {!!item.events?.some(e=>e.kind==='agent_stage')&&<details className="chat-history-detail"><summary>{t('Technical activity','Actividad técnica')}</summary>{item.events.filter(e=>e.kind==='agent_stage').map(e=><div key={e.sequence}>{e.details.stage} · {new Date(e.created_at).toLocaleTimeString()}</div>)}</details>}
  </div>;
}

export default function AIChat({projectId,projectName,projectKind,contextPaths,contextDigest,onReview,onApplied,onApproveContext}:Props) {
  const [items,setItems] = useState<Proposal[]>([]);
  const [draft,setDraft] = useState('');
  const [busy,setBusy] = useState(false);
  const [workingId,setWorkingId] = useState<string|null>(null);
  const [error,setError] = useState('');
  const [skipped,setSkipped] = useState<string[]>([]);
  const [selectedApproval,setSelectedApproval] = useState<string|null>(null);
  const [discarded,setDiscarded] = useState<string[]>([]);

  const [contextOpen,setContextOpen] = useState(false);
  const [insights,setInsights] = useState<RepositoryInsights|null>(null);
  const [selected,setSelected] = useState<string[]>(contextPaths);
  const [preview,setPreview] = useState<ContextPreview|null>(null);
  const bottom = useRef<HTMLDivElement|null>(null);
  async function openContext(){
    try { const result = await getRepositoryInsights(projectId); setInsights(result); setSelected(contextPaths.filter(path=>result.candidates.some(file=>file.path===path))); setPreview(null); setContextOpen(true); } catch(e){setError(String(e));}
  }
  async function toggleContext(){
    if(contextOpen){setContextOpen(false);return;}
    await openContext();
  }
  async function reviewContext(){try{setPreview(await previewRepositoryContext(projectId,selected));}catch(e){setError(String(e));}}
  const [testApproval,setTestApproval] = useState<{id:string; preview:TestPreview}|null>(null);
  useEffect(()=>{let cancelled=false;setItems([]);setError('');setInsights(null);setContextOpen(false);setSelected(contextPaths);setPreview(null);setTestApproval(null);setSkipped([]);setDiscarded([]);setSelectedApproval(null);listProposals(projectId).then(result=>{if(!cancelled){setItems(result.reverse());setSkipped(result.filter(p=>['ready','test_failed'].includes(p.status)&&p.events?.slice(-1)[0]?.kind==='tests_skipped').map(p=>p.id));setDiscarded(result.filter(p=>p.status==='tested'&&p.events?.slice(-1)[0]?.kind==='apply_deferred').map(p=>p.id));}}).catch(e=>{if(!cancelled)setError(String(e));});return()=>{cancelled=true;};},[projectId]);
  useEffect(()=>{
    const pending=items.filter(item=>activeStatuses.includes(item.status));
    if(!pending.length)return;
    let cancelled=false;
    const refresh=async()=>{
      for(const item of pending){
        try{const updated=await getProposal(item.id);if(!cancelled)setItems(old=>old.map(p=>p.id===updated.id?updated:p));}
        catch(e){if(!cancelled)setError(String(e));}
      }
    };
    const timer=window.setInterval(()=>void refresh(),2200);
    return()=>{cancelled=true;window.clearInterval(timer);};
  },[items]);
  async function submit(e:React.FormEvent){
    e.preventDefault();const task=draft.trim();if(!task||busy)return;
    setBusy(true);setError('');
    try{const proposal=await createProposal(projectId,task,contextPaths,contextDigest);setItems(old=>[...old,proposal]);setDraft('');setSelectedApproval(null);window.setTimeout(()=>bottom.current?.scrollIntoView({behavior:'smooth',block:'end'}),50);}
    catch(e){const message=e instanceof Error?e.message:String(e);setError(message);if(needsContext(message))await openContext();}finally{setBusy(false);}
  }
  const latest = items[items.length-1];
  const approvalItem = items.find(item=>item.id===selectedApproval) ?? latest;
  const previewId = approvalItem && ['ready','test_failed'].includes(approvalItem.status) && !skipped.includes(approvalItem.id) && !discarded.includes(approvalItem.id) ? approvalItem.id : null;
  useEffect(()=>{
    setTestApproval(null);
    if(!previewId)return;
    let cancelled=false;
    previewTest(previewId).then(preview=>{if(!cancelled)setTestApproval({id:previewId,preview});}).catch(e=>{if(!cancelled){setError(String(e));setSkipped(old=>[...old,previewId]);}});
    return()=>{cancelled=true;};
  },[projectId,previewId,approvalItem?.attempts]);
  async function approveTests(id:string){if(testApproval?.id!==id||workingId!==null)return;const {preview}=testApproval;setTestApproval(null);setWorkingId(id);setError('');try{const result=await testProposal(id,preview.approval);setItems(old=>old.map(p=>p.id===id?result:p));}catch(e){setError(String(e));setSkipped(old=>[...old,id]);}finally{setWorkingId(null);}}
  async function repair(id:string){
    if(workingId!==null)return;
    setWorkingId(id);setError('');setTestApproval(null);
    try{const result=await repairProposal(id);setItems(old=>old.map(p=>p.id===id?result:p));setSkipped(old=>old.filter(x=>x!==id));setSelectedApproval(id);}
    catch(e){setError(String(e));setSkipped(old=>[...old,id]);}finally{setWorkingId(null);}
  }
  async function defer(id:string, action:'tests'|'apply'){
    if(workingId!==null)return;
    setWorkingId(id);
    try { const result=await deferProposal(id,action);setItems(old=>old.map(p=>p.id===id?result:p));
      if(action==='tests')setSkipped(old=>[...old,id]);else setDiscarded(old=>[...old,id]);
    } catch(e){setError(String(e));}finally{setWorkingId(null);}
  }
  async function apply(id:string){if(workingId!==null)return;setWorkingId(id);setError('');try{const result=await applyProposal(id,projectKind==='existing');setItems(old=>old.map(p=>p.id===id?result:p));onApplied();}catch(e){setError(String(e));}finally{setWorkingId(null);}}
  return <div className="chat-shell">
    <div className="chat-topline"><span><Bot size={15}/> Your coding assistant</span><button title="Choose files to share with AI" onClick={()=>void toggleContext()}><Paperclip size={14}/> Context {contextPaths.length>0?`(${contextPaths.length})`:''}</button></div>
    {contextOpen&&<div className="chat-context-inline">
      <strong>Share project context ({selected.length}/{insights?.candidates.length ?? 0} available, max 8)</strong>
      <p>Context is optional for new files. Only files you review and approve will be sent to the AI.</p>
      {insights?.candidates.length===0&&<p>No files available. You can send a request without context.</p>}
      <div className="chat-context-files">{insights?.candidates.map(file=><label key={file.path}><input type="checkbox" checked={selected.includes(file.path)} disabled={!selected.includes(file.path)&&selected.length>=8} onChange={()=>{setSelected(old=>old.includes(file.path)?old.filter(p=>p!==file.path):[...old,file.path]);setPreview(null);}}/>{file.path}</label>)}</div>
      {preview&&<details><summary>Review exact contents ({preview.total_bytes} bytes)</summary>{preview.files.map(file=><details key={file.path}><summary>{file.path}</summary><pre>{file.content}</pre></details>)}</details>}
      <div className="chat-context-actions"><button type="button" onClick={()=>{onApproveContext([],null);setSelected([]);setPreview(null);setContextOpen(false);}}>Continue without context</button><button type="button" disabled={selected.length===0} onClick={()=>void reviewContext()}>Review selection</button><button type="button" disabled={!preview} onClick={()=>{if(preview){onApproveContext(selected,preview.digest);setContextOpen(false);}}}>Approve context</button></div>
    </div>}
    <div className="chat-scroll">
      {!items.length&&<div className="chat-empty"><Bot size={28}/><h3>What shall we build?</h3><p>Describe a change to your project. I'll prepare the files and ask before running local tests. Nothing is applied without your approval.</p></div>}
      {items.map(item=>{const t=translator(item.task);return <div className="chat-exchange" key={item.id}>
        <div className="chat-user-bubble">{item.task}</div>
        <div className="chat-assistant-message">
          <Conversation item={item} projectName={projectName} onReview={onReview}/>
          {activeStatuses.includes(item.status)&&<div className="chat-inline-status"><LoaderCircle className="chat-spin" size={14}/> {t(describe(item.status),item.status==='queued'?'Esperando a la IA…':'Preparando cambios…')}</div>}
          {item.error&&<div className="chat-error"><span>{item.error}</span>{needsContext(item.error)&&<button className="chat-secondary-action" onClick={()=>{setDraft(item.task);void openContext();}}>{t('Choose project files','Elegir ficheros del proyecto')}</button>}</div>}
          {workingId===item.id&&<div className="chat-inline-status" role="status"><LoaderCircle className="chat-spin" size={14}/> {item.status==='tested'?t('Applying changes…','Aplicando cambios…'):t('Running approved local tests…','Ejecutando tests locales autorizados…')}</div>}
          {item.id!==approvalItem?.id&&['ready','test_failed'].includes(item.status)&&<button className="chat-link" disabled={workingId!==null} onClick={()=>setSelectedApproval(item.id)}>{t('Review command','Revisar comando')}</button>}
          {item.id===approvalItem?.id&&['ready','test_failed'].includes(item.status)&&workingId!==item.id&&(!skipped.includes(item.id)?<>
            <p className="chat-action-text">{item.status==='test_failed'?t('Would you like me to fix the problem, or run the same tests again?','¿Quieres que corrija el problema o vuelva a ejecutar los mismos tests?'):t('May I run the tests to verify these changes?','¿Puedo ejecutar los tests para verificar estos cambios?')}</p>
            {item.status==='test_failed'&&<div className="chat-inline-actions"><button className="chat-inline-primary" disabled={workingId!==null} onClick={()=>void repair(item.id)}>{t('Fix and retry','Corregir y reintentar')}</button></div>}
            <div className="chat-command-card">
              <div className="chat-command-title"><Terminal size={14}/> {t('Run command','Ejecutar comando')} <small>{t('Local','Local')}</small></div>
              {testApproval?.id===item.id?<><pre>{testApproval.preview.command.map(arg=>/^[\w./:=+-]+$/.test(arg)?arg:JSON.stringify(arg)).join(' ')}</pre><p>{t('Runs a temporary copy with your user permissions and Internet access. Review the files first.','Ejecuta una copia temporal con tus permisos de usuario y acceso a Internet. Revisa primero los ficheros.')}</p><div className="chat-inline-actions"><button className="chat-inline-muted" disabled={workingId!==null} onClick={()=>void defer(item.id,'tests')}>{t('Skip','Omitir')}</button><button className="chat-inline-primary" disabled={workingId!==null} onClick={()=>void approveTests(item.id)}>{item.status==='test_failed'?t('Allow retry','Permitir reintento'):t('Allow once','Permitir una vez')}</button></div></>:<><p>{t('Preparing command approval…','Preparando autorización…')}</p><button className="chat-inline-muted" onClick={()=>void defer(item.id,'tests')}>{t('Cancel','Cancelar')}</button></>}
            </div></>:<div className="chat-inline-status">{t('Tests not authorized.','Tests no autorizados.')} <button className="chat-link" onClick={()=>setSkipped(old=>old.filter(id=>id!==item.id))}>{t('Request again','Solicitar de nuevo')}</button></div>)}
          {item.status==='tested'&&workingId!==item.id&&(discarded.includes(item.id)?<div className="chat-inline-status">{t('Changes not applied.','Cambios no aplicados.')} <button className="chat-link" onClick={()=>setDiscarded(old=>old.filter(id=>id!==item.id))}>{t('Review again','Revisar de nuevo')}</button></div>:<>
            <p className="chat-action-text">{t(`Tests passed. Apply the verified changes to ${projectName}?`,`Los tests han pasado. ¿Aplico los cambios a ${projectName}?`)}{projectKind==='existing'?t(' This will write to your registered project.',' Esto escribirá en tu proyecto registrado.'):''}</p>
            <div className="chat-inline-actions"><button className="chat-inline-muted" disabled={workingId!==null} onClick={()=>void defer(item.id,'apply')}>{t('Not now','Ahora no')}</button><button className="chat-inline-primary" disabled={workingId!==null} onClick={()=>void apply(item.id)}><Check size={13}/> {t('Accept changes','Aceptar cambios')}</button></div>
          </>)}
        </div>
      </div>;})}
      <div ref={bottom}/>
    </div>
    {error&&<div className="chat-error chat-global-error" role="alert"><CircleAlert size={14}/>{error}<button onClick={()=>setError('')}><X size={13}/></button></div>}
    <form className="chat-composer" onSubmit={e=>void submit(e)}>
      <textarea aria-label="Ask AI" placeholder="Ask AI to change your project…" rows={3} value={draft} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void submit(e);}}}/>
      <div className="chat-composer-bottom"><span>Changes require your approval</span><button type="submit" aria-label="Send to AI" disabled={!draft.trim()||busy}>{busy?<LoaderCircle className="chat-spin" size={16}/>:<Send size={16}/>}</button></div>
    </form>
  </div>;
}
