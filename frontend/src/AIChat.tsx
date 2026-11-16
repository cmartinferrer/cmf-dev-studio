import { contextFiles, toggleRetryFile, sameContext } from './chatContext';
import { useEffect, useRef, useState } from 'react';
import { Bot, Check, ChevronRight, CircleAlert, FileCode2, LoaderCircle, Paperclip, Send, X } from 'lucide-react';
import { decideGeneration, repairProposal, deferProposal, applyProposal, createProposal, getProposal, listProposals, testProposal, previewTest, type TestPreview, getRepositoryInsights, previewRepositoryContext, type RepositoryInsights, type Proposal, type ProposalChange } from './api';

type Props = { projectId: string; projectName: string; projectKind: 'managed'|'existing'; contextPaths: string[]; activePath: string|null; dirtyPaths: string[]; excluded: string[]; onExclude:(path:string)=>void; onAddContext:(path:string)=>void; revision:number; onReview: (proposalId:string, change: ProposalChange)=>void; onApplied: ()=>void };
const infrastructureFailure = (item:Proposal) => /infrastructure_error|^Runner infrastructure error:/.test((item.test_output??'').split('\n')[0]);
const canRunTests = (item:Proposal) => item.status==='ready'||(item.status==='test_failed'&&infrastructureFailure(item));
const repairCount = (item:Proposal) => item.events?.filter(e=>e.kind==='repair_requested').length??0;
const activeStatuses = ['queued','running'];
const describe = (status: Proposal['status']) => ({queued:'Waiting for the AI…',running:'Preparing changes…',ready:'Changes ready · Approval required',tested:'Tests passed · Ready to review',test_failed:'Tests failed · Review the output',applied:'Changes applied',failed:'Could not prepare changes'})[status];

const needsContext = (error?: string | null) => /Permission required to read and modify|already exists: use modify|Review and approve repository context/i.test(error ?? '');


const transient = (error?:string) => /\b503\b|UNAVAILABLE|high demand/i.test(error ?? '');
const commandText = (args:string[]) => args.map(arg=>/^[\w./:=+-]+$/.test(arg)?arg:JSON.stringify(arg)).join(' ');
const translator = (task:string) => {
  const es = /\b(crea(?:me)?|haz|anade|quiero|puedes|calculadora|modifica|corrige|implementa|por favor|necesito|genera|agrega|elimina|cambia|actualiza|pruebas|ficheros)\b/i.test(task.normalize('NFD').replace(/\p{M}/gu,''));
  return (en:string,spanish:string) => es?spanish:en;
};
function HistoryContext({paths}:{paths?:string[]}) {
  return paths?.length ? <div className="chat-context-tags" style={{marginTop:6,marginBottom:0}}>{paths.map(path=><span className="chat-context-tag" key={path} title={path}><FileCode2 size={13}/><span>{path.split('/').pop()}</span></span>)}</div> : null;
}
function Conversation({item,projectName,onReview}:{item:Proposal;projectName:string;onReview:Props['onReview']}) {
  // Use persisted facts, not additional model calls or invented explanations.
  const t = translator(item.task);
  const events = (item.events ?? []).filter(e=>!['requested','agent_stage'].includes(e.kind));
  const generated = events.filter(e=>['files_generated','repair_ready'].includes(e.kind));
  const lastGenerated = generated[generated.length-1]?.sequence;
  const assistant = (children:React.ReactNode) => <div className="chat-dialog-assistant"><div className="chat-dialog-author"><Bot size={14}/> {t('Assistant','Asistente')}</div>{children}</div>;
  const user = (label:string, paths?:string[]) => <div className="chat-user-bubble chat-dialog-decision">{label}<HistoryContext paths={paths}/></div>;
  const files = <div className="chat-change-card"><div className="chat-change-summary"><strong>{item.changes.length} {t('files','ficheros')}</strong><span>{t('Review in editor','Revisar en el editor')}</span></div>{item.changes.map(change=><button key={change.path} className="chat-change-row" onClick={()=>onReview(item.id,change)}><FileCode2 size={14}/><span>{change.path}</span><small>{change.action}</small><ChevronRight size={13}/></button>)}</div>;
  const output = (value?:string) => value&&<details className="chat-history-detail"><summary>{t('Show output','Ver resultado')}</summary><pre className="chat-test-output">{value}</pre></details>;
  return <div className="chat-dialog">
    {events.map(event=>{const d=event.details;let content:React.ReactNode;
      switch(event.kind){
        case 'files_generated': case 'repair_ready': content=assistant(<><p>{event.kind==='repair_ready'?t('I have prepared a revised proposal.','He preparado una propuesta corregida.'):t(`I have prepared ${d.count ?? item.changes.length} files for your request.`,`He preparado ${d.count ?? item.changes.length} ficheros para tu petición.`)}</p>{event.sequence===lastGenerated&&files}</>);break;
        case 'command_approved': content=<>{assistant(<><p>{t('May I run this command to check the changes?','¿Puedo ejecutar este comando para comprobar los cambios?')}</p>{d.command&&<pre className="chat-history-command">{commandText(d.command)}</pre>}</>)}{user(t('Allow once','Permitir una vez'))}</>;break;
        case 'tests_skipped': content=d.repair_cancelled?<>{user(t('Cancel','Cancelar'))}{assistant(<p>{t('I will leave the failed proposal unchanged.','Dejo la propuesta fallida sin aplicar.')}</p>)}</>:<>{assistant(<p>{t('May I run the tests?','¿Puedo ejecutar los tests?')}</p>)}{user(t('Skip','Omitir'))}{assistant(<p>{t('I will leave the proposal pending.','Dejo la propuesta pendiente.')}</p>)}</>;break;
        case 'tests_passed': content=assistant(<><p>{t('The tests passed successfully.','Los tests han pasado correctamente.')}</p>{output(d.output)}</>);break;
        case 'tests_failed': content=assistant(<><p>{t('The test command failed. The project has not been changed.','La ejecución de los tests ha fallado. No he modificado el proyecto.')}</p>{output(d.output)}</>);break;
        case 'repair_requested': content=<>{assistant(<p>{t('The tests failed. Shall I correct the proposal before testing again?','Los tests han fallado. ¿Quieres que corrija la propuesta antes de volver a probarla?')}</p>)}{user(t('Fix and retry','Corregir y reintentar'))}</>;break;
        case 'apply_deferred': content=<>{assistant(<p>{t(`May I apply the changes to ${projectName}?`,`¿Aplico los cambios a ${projectName}?`)}</p>)}{user(t('Not now','Ahora no'))}</>;break;
        case 'changes_applied': content=<>{assistant(<p>{t(`May I apply the changes to ${projectName}?`,`¿Aplico los cambios a ${projectName}?`)}</p>)}{user(t('Accept changes','Aceptar cambios'))}{assistant(<p>{t(`I have saved ${d.count ?? item.changes.length} files to your project.`,`He guardado ${d.count ?? item.changes.length} ficheros en tu proyecto.`)}</p>)}</>;break;
        case 'generation_failed': case 'repair_failed': content=assistant(<><p>{transient(d.error)?t('The AI model is temporarily overloaded. I could not prepare the changes.','El modelo de IA está temporalmente saturado. No he podido preparar los cambios.'):needsContext(d.error)?t('I need the existing files in context before modifying them.','Necesito que añadas los ficheros existentes al contexto para poder modificarlos.'):t('I could not prepare the changes.','No he podido preparar los cambios.')}</p>{output(d.error)}{event.kind==='generation_failed'&&<p>{t('Would you like me to retry the same request?','¿Quieres que vuelva a intentar la misma petición?')}</p>}</>);break;
        case 'generation_retry_requested': content=user(t('Retry','Reintentar'),d.context_paths ?? item.events?.find(e=>e.kind==='requested')?.details.context_paths ?? item.approved_paths);break;
        case 'generation_cancelled': content=<>{user(t('Cancel','Cancelar'))}{assistant(<p>{t('I will not retry this request.','No volveré a intentar esta petición.')}</p>)}</>;break;
        default:return null;
      }return <div className="chat-dialog-turn" key={event.sequence}>{content}</div>;
    })}
    {item.error&&!events.some(e=>['generation_failed','repair_failed'].includes(e.kind)&&e.details.error===item.error)&&assistant(<><p>{t('An error occurred.','Se ha producido un error.')}</p>{output(item.error)}{item.status==='failed'&&<p>{t('Would you like me to retry the same request?','¿Quieres que vuelva a intentar la misma petición?')}</p>}</>)}
    {!generated.length&&item.changes.length>0&&assistant(files)}
    {!events.some(e=>e.kind==='tests_passed'||e.kind==='tests_failed')&&item.test_output&&assistant(<><p>{item.status==='test_failed'?t('The tests failed.','Los tests han fallado.'):t('Test result','Resultado de los tests')}</p>{output(item.test_output)}</>)}
    {item.status==='applied'&&!events.some(e=>e.kind==='changes_applied')&&assistant(<p>{t('The changes are saved.','Los cambios están guardados.')}</p>)}
    {!!item.events?.some(e=>e.kind==='agent_stage')&&<details className="chat-history-detail"><summary>{t('Technical activity','Actividad técnica')}</summary>{item.events.filter(e=>e.kind==='agent_stage').map(e=><div key={e.sequence}>{e.details.stage} · {new Date(e.created_at).toLocaleTimeString()}</div>)}</details>}
  </div>;
}

function RetryContext({item,candidates,ready,disabled,dirtyPaths,onDecision}:{item:Proposal;candidates:RepositoryInsights['candidates'];ready:boolean;disabled:boolean;dirtyPaths:string[];onDecision:(retry:boolean,paths:string[])=>Promise<void>}) {
  const t=translator(item.task);
  const [selected,setSelected]=useState<string[]>(()=>[...(item.approved_paths??[])]);
  const [open,setOpen]=useState(false);
  const [query,setQuery]=useState('');
  const unavailable=selected.some(path=>!candidates.some(c=>c.path===path));
  const dirty=selected.some(path=>dirtyPaths.includes(path));
  const matches=candidates.filter(c=>c.path.toLowerCase().includes(query.toLowerCase())).slice(0,30);
  const toggle=(path:string)=>setSelected(old=>toggleRetryFile(old,path));
  return <div className="chat-retry-context">
    <small>{t('Retry context','Contexto del reintento')}</small>
    <div className="chat-context-tags">{selected.map(path=><span className="chat-context-tag" key={path} title={path}><FileCode2 size={13}/><span>{path.split('/').pop()}</span><button type="button" disabled={disabled} aria-label={`Remove ${path} from retry context`} onClick={()=>toggle(path)}><X size={12}/></button></span>)}</div>
    <button type="button" className="chat-link" disabled={disabled||!ready} onClick={()=>{setOpen(v=>!v);setQuery('');}}><Paperclip size={14}/> {t('Add context','Añadir contexto')}</button>
    {open&&<div className="chat-context-picker"><input autoFocus aria-label="Search retry files" placeholder={t('Search project files…','Buscar ficheros…')} value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Escape')setOpen(false);if(e.key==='Enter'&&matches[0]){e.preventDefault();toggle(matches[0].path);}}}/><div className="chat-context-results">{matches.map(c=><button type="button" key={c.path} disabled={disabled||(!selected.includes(c.path)&&selected.length>=8)} onClick={()=>toggle(c.path)} title={c.path}><FileCode2 size={14}/><span>{c.path}</span>{selected.includes(c.path)&&<Check size={13}/>}</button>)}</div></div>}
    {dirty&&<small role="alert">{t('Save modified context files before retrying.','Guarda los ficheros modificados antes de reintentar.')}</small>}
    {ready&&unavailable&&<small role="alert">{t('Remove unavailable files before retrying.','Quita los ficheros que ya no están disponibles.')}</small>}
    <div className="chat-inline-actions"><button type="button" className="chat-inline-muted" disabled={disabled} onClick={()=>void onDecision(false,selected)}>{t('Cancel','Cancelar')}</button><button type="button" className="chat-inline-primary" disabled={disabled||!ready||dirty||unavailable} onClick={()=>void onDecision(true,selected)}>{t('Retry','Reintentar')}</button></div>
  </div>;
}

export default function AIChat({projectId,projectName,projectKind,contextPaths,activePath,dirtyPaths,excluded,onExclude,onAddContext,revision,onReview,onApplied}:Props) {
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
  const [query,setQuery] = useState('');
  const [inventoryReady,setInventoryReady] = useState(false);
  const bottom = useRef<HTMLDivElement|null>(null);
  useEffect(()=>{let cancelled=false;setInventoryReady(false);getRepositoryInsights(projectId).then(result=>{if(!cancelled){setInsights(result);setInventoryReady(true);}}).catch(e=>{if(!cancelled){setInsights(null);setInventoryReady(true);setError(String(e));}});return()=>{cancelled=true;};},[projectId,revision]);
  const candidates=insights?.candidates??[];
  const eligibleActive=activePath&&candidates.some(c=>c.path===activePath)?activePath:null;
  const manual=contextPaths.filter(path=>candidates.some(c=>c.path===path));
  const paths=contextFiles(manual,eligibleActive,excluded);
  const mention=draft.match(/(?:^|\s)@([^\s@]*)$/);
  const pickerOpen=contextOpen||!!mention;
  const search=mention?mention[1]:query;
  const matches=candidates.filter(c=>c.path.toLowerCase().includes(search.toLowerCase())).slice(0,30);
  async function openContext(){setQuery('');setContextOpen(true);}
  function choose(path:string){if(!manual.includes(path)&&manual.length>=8)return;onAddContext(path);if(mention)setDraft(old=>old.slice(0,old.length-mention[0].length)+(mention[0].startsWith(' ')?' ':''));setContextOpen(false);setQuery('');}
  const [testApproval,setTestApproval] = useState<{id:string; preview:TestPreview}|null>(null);
  useEffect(()=>{let cancelled=false;setItems([]);setError('');setContextOpen(false);setQuery('');setTestApproval(null);setSkipped([]);setDiscarded([]);setSelectedApproval(null);listProposals(projectId).then(result=>{if(!cancelled){setItems(result.reverse());setSkipped(result.filter(p=>['ready','test_failed'].includes(p.status)&&p.events?.slice(-1)[0]?.kind==='tests_skipped').map(p=>p.id));setDiscarded(result.filter(p=>p.status==='tested'&&p.events?.slice(-1)[0]?.kind==='apply_deferred').map(p=>p.id));}}).catch(e=>{if(!cancelled)setError(String(e));});return()=>{cancelled=true;};},[projectId]);
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
    e.preventDefault();const task=draft.trim();if(!task||busy||workingId!==null||!inventoryReady)return;
    if(dirtyPaths.some(path=>paths.includes(path))){setError('Save modified context files before sending, or remove their tags.');return;}
    setBusy(true);setError('');
    try{const preview=paths.length?await previewRepositoryContext(projectId,paths):null;const proposal=await createProposal(projectId,task,paths,preview?.digest??null);setItems(old=>[...old,proposal]);setDraft('');setSelectedApproval(null);window.setTimeout(()=>bottom.current?.scrollIntoView({behavior:'smooth',block:'end'}),50);}
    catch(e){const message=e instanceof Error?e.message:String(e);setError(message);if(needsContext(message))await openContext();}finally{setBusy(false);}
  }
  const latest = items[items.length-1];
  const approvalItem = items.find(item=>item.id===selectedApproval) ?? latest;
  const previewId = approvalItem && canRunTests(approvalItem) && !skipped.includes(approvalItem.id) && !discarded.includes(approvalItem.id) ? approvalItem.id : null;
  useEffect(()=>{
    setTestApproval(null);
    if(!previewId)return;
    let cancelled=false;
    previewTest(previewId).then(preview=>{if(!cancelled)setTestApproval({id:previewId,preview});}).catch(e=>{if(!cancelled){setError(String(e));setSkipped(old=>[...old,previewId]);}});
    return()=>{cancelled=true;};
  },[projectId,previewId,approvalItem?.attempts,approvalItem?.status]);
  async function generationDecision(item:Proposal,retry:boolean, selected:string[]){
    const useCurrent=retry&&!sameContext(selected,item.approved_paths??[]);
    if(workingId!==null||busy)return;
    if(retry&&dirtyPaths.some(path=>selected.includes(path))){setError('Save modified context files before retrying.');return;}
    setWorkingId(item.id);setError('');
    try{const preview=useCurrent&&selected.length?await previewRepositoryContext(projectId,selected):null;const result=await decideGeneration(item.id,retry,useCurrent?selected:undefined,preview?.digest);setItems(old=>old.map(p=>p.id===item.id?result:p));if(retry)setSelectedApproval(item.id);}
    catch(e){setError(e instanceof Error?e.message:String(e));}finally{setWorkingId(null);}
  }
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
    <div className="chat-topline"><span><Bot size={15}/> Your coding assistant</span></div>
    <div className="chat-scroll">
      {!items.length&&<div className="chat-empty"><Bot size={28}/><h3>What shall we build?</h3><p>Describe a change to your project. I'll prepare the files and ask before running local tests. Nothing is applied without your approval.</p></div>}
      {items.map(item=>{const t=translator(item.task);return <div className="chat-exchange" key={item.id}>
        <div className="chat-user-bubble">{item.task}<HistoryContext paths={item.events?.find(e=>e.kind==='requested')?.details.context_paths ?? item.approved_paths}/></div>
        <div className="chat-assistant-message">
          <Conversation item={item} projectName={projectName} onReview={onReview}/>
          {activeStatuses.includes(item.status)&&<div className="chat-inline-status"><LoaderCircle className="chat-spin" size={14}/> {t(describe(item.status),item.status==='queued'?'Esperando a la IA…':'Preparando cambios…')}</div>}
          {item.status==='failed'&&!item.events?.some(e=>e.kind==='generation_cancelled')&&<RetryContext key={`${item.id}:${item.events?.slice(-1)[0]?.sequence??0}`} item={item} candidates={candidates} ready={inventoryReady} disabled={workingId!==null||busy} dirtyPaths={dirtyPaths} onDecision={(retry,selected)=>generationDecision(item,retry,selected)}/>}

          {workingId===item.id&&item.status!=='failed'&&<div className="chat-inline-status" role="status"><LoaderCircle className="chat-spin" size={14}/> {item.status==='tested'?t('Applying changes…','Aplicando cambios…'):t('Running approved local tests…','Ejecutando tests locales autorizados…')}</div>}
          {item.id!==approvalItem?.id&&['ready','test_failed'].includes(item.status)&&<button className="chat-link" disabled={workingId!==null} onClick={()=>setSelectedApproval(item.id)}>{t('Review command','Revisar comando')}</button>}
          {item.id===approvalItem?.id&&['ready','test_failed'].includes(item.status)&&workingId!==item.id&&(!skipped.includes(item.id)?<>
            {item.status==='test_failed'&&!infrastructureFailure(item)?<>
              <p className="chat-action-text">{repairCount(item)>=3?t('I could not resolve the failure after three repair attempts. Start a new request to continue.','No he podido resolver el fallo tras tres intentos de corrección. Inicia una nueva petición para continuar.'):t('The tests failed. Shall I correct the proposal before testing again?','Los tests han fallado. ¿Quieres que corrija la propuesta antes de volver a probarla?')}</p>
              <div className="chat-inline-actions"><button className="chat-inline-muted" disabled={workingId!==null} onClick={()=>void defer(item.id,'tests')}>{t('Cancel','Cancelar')}</button>{repairCount(item)<3&&<button className="chat-inline-primary" disabled={workingId!==null} onClick={()=>void repair(item.id)}>{t('Fix and retry','Corregir y reintentar')}</button>}</div>
            </>:<>
              <p className="chat-action-text">{item.status==='test_failed'?t('The runner failed. May I try the command again?','Ha fallado el entorno de ejecución. ¿Puedo volver a ejecutar el comando?'):t('May I run this command to check the changes?','¿Puedo ejecutar este comando para comprobar los cambios?')}</p>
              {testApproval?.id===item.id?<><pre className="chat-history-command">{commandText(testApproval.preview.command)}</pre><small>{t('Temporary copy, local user permissions and Internet access.','Copia temporal, permisos de usuario locales y acceso a Internet.')}</small><div className="chat-inline-actions"><button className="chat-inline-muted" disabled={workingId!==null} onClick={()=>void defer(item.id,'tests')}>{t('Skip','Omitir')}</button><button className="chat-inline-primary" disabled={workingId!==null} onClick={()=>void approveTests(item.id)}>{t('Allow once','Permitir una vez')}</button></div></>:<p>{t('Preparing command approval…','Preparando autorización…')}</p>}
            </>}
          </>:<div className="chat-inline-status">{item.status==='test_failed'?t('Repair paused.','Corrección detenida.'):t('Tests not authorized.','Tests no autorizados.')} <button className="chat-link" onClick={()=>setSkipped(old=>old.filter(id=>id!==item.id))}>{t('Request again','Solicitar de nuevo')}</button></div>)}
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
      {paths.length>0&&<div className="chat-context-tags">{paths.map(path=><span key={path} className={`chat-context-tag ${path===eligibleActive&&!manual.includes(path)?'automatic':''}`} title={path}><FileCode2 size={13}/><span>{path.split('/').pop()}</span><button type="button" aria-label={`Remove ${path} from context`} disabled={busy} onClick={()=>onExclude(path)}><X size={12}/></button></span>)}</div>}
      {pickerOpen&&<div className="chat-context-picker"><input aria-label="Search project files" placeholder="Search project files…" value={search} onChange={e=>{if(mention)setDraft(old=>old.slice(0,old.length-mention[1].length)+e.target.value);else setQuery(e.target.value);}} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();if(matches[0])choose(matches[0].path);}if(e.key==='Escape'){setContextOpen(false);if(mention)setDraft(old=>old.slice(0,old.length-mention[0].length));}}}/><div className="chat-context-results">{matches.map(c=><button type="button" key={c.path} disabled={busy||(!manual.includes(c.path)&&manual.length>=8)} onClick={()=>choose(c.path)} title={c.path}><FileCode2 size={14}/><span>{c.path}</span>{paths.includes(c.path)&&<Check size={13}/>}</button>)}{!matches.length&&<small>No eligible files found</small>}</div></div>}
      <textarea aria-label="Ask AI" placeholder="Ask AI to change your project…" rows={3} value={draft} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Escape'&&pickerOpen){setContextOpen(false);if(mention)setDraft(old=>old.slice(0,old.length-mention[0].length));}if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();if(mention&&matches[0])choose(matches[0].path);else void submit(e);}}}/>
      <div className="chat-composer-bottom"><div className="chat-context-tools"><button type="button" className="chat-add-context" disabled={busy} onClick={()=>{setQuery('');setContextOpen(v=>!v);}}><Paperclip size={14}/> Add context</button></div><button type="submit" aria-label="Send to AI" disabled={!draft.trim()||busy||workingId!==null||!inventoryReady}>{busy?<LoaderCircle className="chat-spin" size={16}/>:<Send size={16}/>}</button></div>
    </form>
  </div>;
}
