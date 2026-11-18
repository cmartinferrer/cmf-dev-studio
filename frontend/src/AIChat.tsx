import { chatDay, chatTime } from './chatDates';
import { terminalTask, type TerminalContext } from './terminalContext';
import type { TerminalSession } from './terminalSessions';
import { contextFiles, toggleRetryFile, sameContext } from './chatContext';
import { useEffect, useRef, useState } from 'react';
import { Bot, History, Plus, Ellipsis, Check, ChevronRight, CircleAlert, FileCode2, LoaderCircle, Paperclip, Send, X, Terminal } from 'lucide-react';
import { listConversations, createConversation, renameConversation, removeConversation, type ChatConversation, decideExploration, prepareProposalPython, decideGeneration, repairProposal, deferProposal, applyProposal, createProposal, getProposal, listProposals, testProposal, previewTest, type TestPreview, getRepositoryInsights, previewRepositoryContext, type RepositoryInsights, type Proposal, type ProposalChange } from './api';

type Props = { onConversationChange:()=>void; terminalContext:TerminalContext[]; terminalSessions:TerminalSession[]; onAttachTerminal:(id:number)=>void; onRemoveTerminal:(id:number)=>void; onClearTerminals:()=>void; askTerminal:number; onAskHandled:()=>void; projectId: string; projectName: string; contextPaths: string[]; activePaths: string[]; dirtyPaths: string[]; excluded: string[]; onExclude:(path:string)=>void; onAddContext:(path:string)=>void; revision:number; onReview: (proposalId:string, change: ProposalChange)=>void; onApplied: ()=>void };
const infrastructureFailure = (item:Proposal) => /infrastructure_error|^Runner infrastructure error:/.test((item.test_output??'').split('\n')[0]);
const canRunTests = (item:Proposal) => item.status==='ready'||(item.status==='test_failed'&&infrastructureFailure(item));
const repairCount = (item:Proposal) => item.events?.filter(e=>e.kind==='repair_requested').length??0;
const activeStatuses = ['queued','running'];
const describe = (status: Proposal['status']) => ({awaiting_exploration:'Waiting for permission',answered:'Answered',queued:'Waiting for the AI…',running:'Preparing changes…',ready:'Changes ready · Approval required',tested:'Tests passed · Ready to review',test_failed:'Tests failed · Review the output',applied:'Changes applied',failed:'Could not prepare changes'})[status];

const needsContext = (error?: string | null) => /Permission required to read and modify|already exists: use modify|Review and approve repository context/i.test(error ?? '');


const transient = (error?:string) => /\b503\b|UNAVAILABLE|high demand/i.test(error ?? '');
const commandText = (args:string[]) => args.map(arg=>/^[\w./:=+-]+$/.test(arg)?arg:JSON.stringify(arg)).join(' ');
const translator = (task:string, language?:string) => {
  const es = /\b(crea(?:me)?|haz|anade|quiero|puedes|calculadora|modifica|corrige|implementa|por favor|necesito|genera|agrega|elimina|cambia|actualiza|pruebas|ficheros|analiza|arregla)\b/i.test(task.normalize('NFD').replace(/\p{M}/gu,''));
  return (en:string,spanish:string) => (language ? language==='Spanish' : es)?spanish:en;
};
function HistoryContext({paths}:{paths?:string[]}) {
  return paths?.length ? <div className="chat-context-tags" style={{marginTop:6,marginBottom:0}}>{paths.map(path=><span className="chat-context-tag" key={path} title={path}><FileCode2 size={13}/><span>{path.split('/').pop()}</span></span>)}</div> : null;
}
function Conversation({item,projectName,onReview}:{item:Proposal;projectName:string;onReview:Props['onReview']}) {
  // Use persisted facts, not additional model calls or invented explanations.
  const t = translator(item.task,item.assistant_language);
  const events = (item.events ?? []).filter(e=>!['requested','agent_stage','exploration_tool'].includes(e.kind));
  const generated = events.filter(e=>['files_generated','repair_ready'].includes(e.kind));
  const lastGenerated = generated[generated.length-1]?.sequence;
  const assistant = (children:React.ReactNode) => <div className="chat-dialog-assistant"><div className="chat-dialog-author"><Bot size={14}/> {t('Assistant','Asistente')}</div>{children}</div>;
  const user = (label:string, paths?:string[]) => <div className="chat-user-bubble chat-dialog-decision">{label}<HistoryContext paths={paths}/></div>;
  const files = <div className="chat-change-card"><div className="chat-change-summary"><strong>{item.changes.length} {item.changes.length===1?t('file','fichero'):t('files','ficheros')}</strong><span>{t('Review in editor','Revisar en el editor')}</span></div>{item.changes.map(change=><button key={change.path} className="chat-change-row" onClick={()=>onReview(item.id,change)}><FileCode2 size={14}/><span>{change.path}</span><small>{change.action}</small><ChevronRight size={13}/></button>)}</div>;
  const output = (value?:string) => value&&<details className="chat-history-detail"><summary>{t('Show output','Ver resultado')}</summary><pre className="chat-test-output">{value}</pre></details>;
  return <div className="chat-dialog">
    {events.map((event,index)=>{const d=event.details;let content:React.ReactNode;
      switch(event.kind){
        case 'assistant_response':  content=assistant(<p style={{whiteSpace:'pre-wrap'}}>{d.message || t('I need permission to explore the project.','Necesito permiso para explorar el proyecto.')}</p>);break;
        case 'exploration_allowed': content=user(t('Allow exploration','Permitir exploración'));break;
        case 'exploration_denied': content=user(t('Deny exploration','Denegar exploración'));break;
        case 'files_generated': case 'repair_ready': content=assistant(<><p>{event.kind==='repair_ready'?t('I have prepared a revised proposal.','He preparado una propuesta corregida.'):t(`I have prepared ${d.count ?? item.changes.length} ${(d.count ?? item.changes.length)===1?'file':'files'} for your request.`,`He preparado ${d.count ?? item.changes.length} ${(d.count ?? item.changes.length)===1?'fichero':'ficheros'} para tu petición.`)}</p>{event.sequence===lastGenerated&&files}</>);break;
        case 'command_approved': content=<>{assistant(<><p>{t('May I run this command to check the changes?','¿Puedo ejecutar este comando para comprobar los cambios?')}</p>{d.command&&<pre className="chat-history-command">{commandText(d.command)}</pre>}</>)}{user(t('Allow once','Permitir una vez'))}</>;break;
        case 'tests_skipped': content=d.repair_cancelled?<>{user(t('Cancel','Cancelar'))}{assistant(<p>{t('I will leave the failed proposal unchanged.','Dejo la propuesta fallida sin aplicar.')}</p>)}</>:<>{assistant(<p>{t('May I run the tests?','¿Puedo ejecutar los tests?')}</p>)}{user(t('Skip','Omitir'))}{assistant(<p>{t('I will leave the proposal pending.','Dejo la propuesta pendiente.')}</p>)}</>;break;
        case 'tests_passed': content=assistant(<><p>{t('The tests passed successfully.','Los tests han pasado correctamente.')}</p>{output(d.output)}</>);break;
        case 'tests_failed': content=assistant(<><p>{t('The test command failed. The project has not been changed.','La ejecución de los tests ha fallado. No he modificado el proyecto.')}</p>{output(d.output)}</>);break;
        case 'repair_requested': content=<>{assistant(<p>{t('The tests failed. Shall I correct the proposal before testing again?','Los tests han fallado. ¿Quieres que corrija la propuesta antes de volver a probarla?')}</p>)}{user(t('Fix and retry','Corregir y reintentar'))}</>;break;
        case 'apply_deferred': content=<>{assistant(<p>{t(`May I apply the changes to ${projectName}?`,`¿Aplico los cambios a ${projectName}?`)}</p>)}{user(t('Not now','Ahora no'))}</>;break;
        case 'changes_applied': content=<>{assistant(<p>{t(`May I apply the changes to ${projectName}?`,`¿Aplico los cambios a ${projectName}?`)}</p>)}{user(t('Accept changes','Aceptar cambios'))}{assistant(<p>{t(`I have saved ${d.count ?? item.changes.length} ${(d.count ?? item.changes.length)===1?'file':'files'} to your project.`,`He guardado ${d.count ?? item.changes.length} ${(d.count ?? item.changes.length)===1?'fichero':'ficheros'} en tu proyecto.`)}</p>)}</>;break;
        case 'environment_offered': content=assistant(<p>{d.environment==='jvm'?t('May I build and test the project? This runs build scripts in your project and may download dependencies.','¿Quieres que compile y pruebe el proyecto? Se ejecutarán los scripts de compilación en tu proyecto y se podrán descargar dependencias.'):t('Shall I prepare the Python environment so you can run your program? This may install dependencies from the Internet.','¿Quieres que prepare el entorno Python para ejecutar el programa? Puede ser necesario descargar e instalar dependencias.')}</p>);break;
        case 'environment_approved': content=user(d.environment==='jvm'?t('Prepare project','Preparar proyecto'):t('Prepare environment','Preparar entorno'));break;
        case 'environment_skipped': content=user(t('Not now','Ahora no'));break;
        case 'environment_ready': content=assistant(<p>{d.environment==='jvm'?t('The project has been built and tested successfully.','El proyecto se ha compilado y probado correctamente.'):t('Your Python environment is ready. Restart the terminal if it is already open.','El entorno Python está listo. Si tienes el terminal abierto, reinícialo.')}</p>);break;
        case 'environment_failed': content=assistant(<><p>{t('I could not prepare the environment. Your files are saved.','No he podido preparar el entorno. Tus ficheros están guardados.')}</p>{output(d.error)}</>);break;
        case 'layout_changed': content=assistant(<p>{t('The project layout changed. Please submit a new request.','La estructura del proyecto ha cambiado. Envía una nueva petición.')}</p>);break;
        case 'generation_failed': case 'repair_failed': content=assistant(<><p>{transient(d.error)?t('The AI model is temporarily overloaded. I could not prepare the changes.','El modelo de IA está temporalmente saturado. No he podido preparar los cambios.'):needsContext(d.error)?t('I need the existing files in context before modifying them.','Necesito que añadas los ficheros existentes al contexto para poder modificarlos.'):t('I could not prepare the changes.','No he podido preparar los cambios.')}</p>{output(d.error)}{event.kind==='generation_failed'&&<p>{t('Would you like me to retry the same request?','¿Quieres que vuelva a intentar la misma petición?')}</p>}</>);break;
        case 'generation_retry_requested': content=user(t('Retry','Reintentar'),d.context_paths ?? item.events?.find(e=>e.kind==='requested')?.details.context_paths ?? item.approved_paths);break;
        case 'generation_cancelled': content=<>{user(t('Cancel','Cancelar'))}{assistant(<p>{t('I will not retry this request.','No volveré a intentar esta petición.')}</p>)}</>;break;
        default:return null;
      }return <div className="chat-dialog-turn" key={event.sequence}>{chatDay(event.created_at)!==chatDay(index?events[index-1].created_at:item.created_at)&&<div className="chat-day">{chatDay(event.created_at)}</div>}{content}<time className="chat-time" dateTime={event.created_at}>{chatTime(event.created_at)}</time></div>;
    })}
    {item.error&&!events.some(e=>['generation_failed','repair_failed','layout_changed'].includes(e.kind)&&e.details.error===item.error)&&assistant(<><p>{t('An error occurred.','Se ha producido un error.')}</p>{output(item.error)}{item.status==='failed'&&<p>{t('Would you like me to retry the same request?','¿Quieres que vuelva a intentar la misma petición?')}</p>}</>)}
    {!generated.length&&item.changes.length>0&&assistant(files)}
    {!events.some(e=>e.kind==='tests_passed'||e.kind==='tests_failed')&&item.test_output&&assistant(<><p>{item.status==='test_failed'?t('The tests failed.','Los tests han fallado.'):t('Test result','Resultado de los tests')}</p>{output(item.test_output)}</>)}
    {item.status==='applied'&&!events.some(e=>e.kind==='changes_applied')&&assistant(<p>{t('The changes are saved.','Los cambios están guardados.')}</p>)}
    {!!item.events?.some(e=>['agent_stage','exploration_tool'].includes(e.kind))&&<details className="chat-history-detail"><summary>{t('Technical activity','Actividad técnica')}</summary>{item.events.filter(e=>['agent_stage','exploration_tool'].includes(e.kind)).map(e=><div key={e.sequence}>{e.details.stage} {e.details.query} · {chatTime(e.created_at,true)}</div>)}</details>}
  </div>;
}

const retryPaths = (item:Proposal) => item.assistant_language ? ([...(item.events??[])].reverse().find(e=>['requested','generation_retry_requested'].includes(e.kind)&&e.details.context_paths)?.details.context_paths??[]) : (item.approved_paths??[]);

function RetryContext({item,candidates,ready,disabled,dirtyPaths,onDecision}:{item:Proposal;candidates:RepositoryInsights['candidates'];ready:boolean;disabled:boolean;dirtyPaths:string[];onDecision:(retry:boolean,paths:string[])=>Promise<void>}) {
  const t=translator(item.task,item.assistant_language);
  const [selected,setSelected]=useState<string[]>(()=>[...retryPaths(item)]);
  const [open,setOpen]=useState(false);
  const [query,setQuery]=useState('');
  const unavailable=selected.some(path=>!candidates.some(c=>c.path===path));
  const dirty=selected.some(path=>dirtyPaths.includes(path));
  const matches=candidates.filter(c=>c.path.toLowerCase().includes(query.toLowerCase())).slice(0,30);
  const toggle=(path:string)=>setSelected(old=>toggleRetryFile(old,path));
  return <div className="chat-retry-context">
    <small>{t('Retry context','Contexto del reintento')}</small>{item.terminal_context?.map(t=><details key={t.id} className="chat-history-detail"><summary>{t.name} · Original terminal snapshot</summary><pre className="chat-test-output">{t.output}</pre></details>)}
    <div className="chat-context-tags">{selected.map(path=><span className="chat-context-tag" key={path} title={path}><FileCode2 size={13}/><span>{path.split('/').pop()}</span><button type="button" disabled={disabled} aria-label={`Remove ${path} from retry context`} onClick={()=>toggle(path)}><X size={12}/></button></span>)}</div>
    <button type="button" className="chat-link" disabled={disabled||!ready} onClick={()=>{setOpen(v=>!v);setQuery('');}}><Paperclip size={14}/> {t('Add context','Añadir contexto')}</button>
    {open&&<div className="chat-context-picker"><input autoFocus aria-label="Search retry files" placeholder={t('Search project files…','Buscar ficheros…')} value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Escape')setOpen(false);if(e.key==='Enter'&&matches[0]){e.preventDefault();toggle(matches[0].path);}}}/><div className="chat-context-results">{matches.map(c=><button type="button" key={c.path} disabled={disabled||(!selected.includes(c.path)&&selected.length>=8)} onClick={()=>toggle(c.path)} title={c.path}><FileCode2 size={14}/><span>{c.path}</span>{selected.includes(c.path)&&<Check size={13}/>}</button>)}</div></div>}
    {dirty&&<small role="alert">{t('Save modified context files before retrying.','Guarda los ficheros modificados antes de reintentar.')}</small>}
    {ready&&unavailable&&<small role="alert">{t('Remove unavailable files before retrying.','Quita los ficheros que ya no están disponibles.')}</small>}
    <div className="chat-inline-actions"><button type="button" className="chat-inline-muted" disabled={disabled} onClick={()=>void onDecision(false,selected)}>{t('Cancel','Cancelar')}</button><button type="button" className="chat-inline-primary" disabled={disabled||!ready||dirty||unavailable} onClick={()=>void onDecision(true,selected)}>{t('Retry','Reintentar')}</button></div>
  </div>;
}

function ConversationChat({projectId,projectName,contextPaths,activePaths,dirtyPaths,excluded,onExclude,onAddContext,revision,onReview,onApplied,terminalContext,terminalSessions,onAttachTerminal,onRemoveTerminal,onClearTerminals,askTerminal,onAskHandled,conversationId,onBusy,onSubmitted}:Props & {conversationId:string;onBusy:(value:boolean)=>void;onSubmitted:()=>void}) {
  const [items,setItems] = useState<Proposal[]>([]);
  const [loading,setLoading]=useState(true);
  const [draft,setDraft] = useState('');
  useEffect(()=>{if(askTerminal){setDraft(old=>old||terminalTask(items[items.length-1]?.task??'',navigator.language));onAskHandled();}},[askTerminal]);
  const [busy,setBusy] = useState(false);
  const [workingId,setWorkingId] = useState<string|null>(null);
  const [error,setError] = useState('');
  const [skipped,setSkipped] = useState<string[]>([]);
  const [selectedApproval,setSelectedApproval] = useState<string|null>(null);
  const [discarded,setDiscarded] = useState<string[]>([]);

  useEffect(()=>{onBusy(loading||busy||workingId!==null||items.some(item=>activeStatuses.includes(item.status)));},[loading,busy,workingId,items]);
  const [contextOpen,setContextOpen] = useState(false);
  const [insights,setInsights] = useState<RepositoryInsights|null>(null);
  const [query,setQuery] = useState('');
  const [inventoryReady,setInventoryReady] = useState(false);
  const bottom = useRef<HTMLDivElement|null>(null);
  useEffect(()=>{let cancelled=false;setInventoryReady(false);getRepositoryInsights(projectId).then(result=>{if(!cancelled){setInsights(result);setInventoryReady(true);}}).catch(e=>{if(!cancelled){setInsights(null);setInventoryReady(true);setError(String(e));}});return()=>{cancelled=true;};},[projectId,revision]);
  const candidates=insights?.candidates??[];
  const eligibleActive=activePaths.filter(path=>candidates.some(c=>c.path===path));
  const manual=contextPaths.filter(path=>candidates.some(c=>c.path===path));
  const paths=contextFiles(manual,eligibleActive,excluded);
  const mention=draft.match(/(?:^|\s)@([^\s@]*)$/);
  const pickerOpen=contextOpen||!!mention;
  const search=mention?mention[1]:query;
  const matches=candidates.filter(c=>c.path.toLowerCase().includes(search.toLowerCase())).slice(0,30);
  async function openContext(){setQuery('');setContextOpen(true);}
  function choose(path:string){if(!manual.includes(path)&&manual.length>=8)return;onAddContext(path);if(mention)setDraft(old=>old.slice(0,old.length-mention[0].length)+(mention[0].startsWith(' ')?' ':''));setContextOpen(false);setQuery('');}
  const [testApproval,setTestApproval] = useState<{id:string; preview:TestPreview}|null>(null);
  useEffect(()=>{let cancelled=false;setLoading(true);setItems([]);setError('');setContextOpen(false);setQuery('');setTestApproval(null);setSkipped([]);setDiscarded([]);setSelectedApproval(null);listProposals(projectId,conversationId).then(result=>{if(!cancelled){setItems(result.reverse());setSkipped(result.filter(p=>['ready','test_failed'].includes(p.status)&&p.events?.slice(-1)[0]?.kind==='tests_skipped').map(p=>p.id));setDiscarded(result.filter(p=>p.status==='tested'&&p.events?.slice(-1)[0]?.kind==='apply_deferred').map(p=>p.id));}}).catch(e=>{if(!cancelled)setError(String(e));}).finally(()=>{if(!cancelled)setLoading(false);});return()=>{cancelled=true;};},[projectId]);
  useEffect(()=>{if(!revision)return;let cancelled=false;listProposals(projectId,conversationId).then(result=>{if(!cancelled)setItems(result.reverse());}).catch(e=>{if(!cancelled)setError(String(e));});return()=>{cancelled=true;};},[projectId,revision]);
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
    e.preventDefault();const task=draft.trim();if(!task||loading||busy||workingId!==null||!inventoryReady)return;
    if(dirtyPaths.length){setError('Save modified files before sending so the assistant can inspect the current project.');return;}
    setBusy(true);setError('');
    try{const preview=paths.length?await previewRepositoryContext(projectId,paths):null;const proposal=await createProposal(projectId,task,paths,preview?.digest??null,terminalContext,translator(task)(items.slice().reverse().find(item=>item.assistant_language)?.assistant_language || (navigator.language.startsWith('es')?'Spanish':'English'),'Spanish'),conversationId);onSubmitted();onClearTerminals();setItems(old=>[...old,proposal]);setDraft('');setSelectedApproval(null);window.setTimeout(()=>bottom.current?.scrollIntoView({behavior:'smooth',block:'end'}),50);}
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
    const useCurrent=retry&&!sameContext(selected,retryPaths(item));
    if(workingId!==null||busy)return;
    if(retry&&dirtyPaths.some(path=>selected.includes(path))){setError('Save modified context files before retrying.');return;}
    setWorkingId(item.id);setError('');
    try{const preview=useCurrent&&selected.length?await previewRepositoryContext(projectId,selected):null;const result=await decideGeneration(item.id,retry,useCurrent?selected:undefined,preview?.digest);setItems(old=>old.map(p=>p.id===item.id?result:p));if(retry)setSelectedApproval(item.id);}
    catch(e){setError(e instanceof Error?e.message:String(e));}finally{setWorkingId(null);}
  }
  async function explore(item:Proposal, allow:boolean){
    if(workingId!==null||busy)return;
    if(allow&&dirtyPaths.length){setError('Save modified files before authorizing exploration.');return;}
    setWorkingId(item.id);setError('');
    try{const result=await decideExploration(item.id,allow);setItems(old=>old.map(p=>p.id===item.id?result:p));}
    catch(e){setError(String(e));}finally{setWorkingId(null);}
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
  async function apply(id:string){if(workingId!==null)return;setWorkingId(id);setError('');try{const result=await applyProposal(id);setItems(old=>old.map(p=>p.id===id?result:p));onApplied();}catch(e){setError(String(e));}finally{setWorkingId(null);}}
  async function preparePython(id:string, confirmed:boolean){
    if(workingId!==null)return;
    setWorkingId(id);setError('');
    try{const result=await prepareProposalPython(id,confirmed);setItems(old=>old.map(p=>p.id===id?result:p));onApplied();}
    catch(e){setError(String(e));}finally{setWorkingId(null);}
  }
  return <div className="chat-shell">

    <div className="chat-scroll">
      {!items.length&&<div className="chat-empty"><Bot size={28}/><h3>What shall we build?</h3><p>Ask a question, paste an error, or request a change. I can investigate your project with permission. Nothing is applied without your approval.</p></div>}
      {items.map((item,index)=>{const t=translator(item.task,item.assistant_language);const setupEvent=item.events?.filter(e=>e.kind.startsWith("environment_")).slice(-1)[0];const setup=setupEvent?.kind;const jvm=setupEvent?.details.environment==='jvm';return <div className="chat-exchange" key={item.id}>
        {(index===0||chatDay(items[index-1].created_at)!==chatDay(item.created_at))&&<div className="chat-day">{chatDay(item.created_at)}</div>}
        <div className="chat-user-bubble">{item.task}<time className="chat-time" dateTime={item.created_at}>{chatTime(item.created_at)}</time><HistoryContext paths={item.events?.find(e=>e.kind==='requested')?.details.context_paths ?? item.approved_paths}/>{item.terminal_context?.map(t=><details key={t.id} className="chat-history-detail"><summary><Terminal size={13}/> {t.name}</summary><pre className="chat-test-output">{t.output}</pre></details>)}</div>
        <div className="chat-assistant-message">
          <Conversation item={item} projectName={projectName} onReview={onReview}/>
          {item.status==='awaiting_exploration'&&<div className="chat-change-card"><p>{t('Allow read-only project exploration? Relevant source may be sent to the AI provider. No commands or edits are authorized.','¿Permites explorar el proyecto en modo lectura? El código relevante podrá enviarse al proveedor de IA. No se autorizan comandos ni modificaciones.')}</p><div className="chat-inline-actions"><button className="chat-inline-muted" disabled={workingId!==null||busy} onClick={()=>void explore(item,false)}>{t('Deny','Denegar')}</button><button className="chat-inline-primary" disabled={workingId!==null||busy} onClick={()=>void explore(item,true)}>{t('Allow once','Permitir una vez')}</button></div></div>}
          {item.status==='applied'&&['environment_offered','environment_failed'].includes(setup??'')&&workingId!==item.id&&<div className="chat-inline-actions"><button className="chat-inline-muted" disabled={workingId!==null||busy} onClick={()=>void preparePython(item.id,false)}>{t('Not now','Ahora no')}</button><button className="chat-inline-primary" disabled={workingId!==null||busy} onClick={()=>void preparePython(item.id,true)}>{setup==='environment_failed'?t('Retry','Reintentar'):jvm?t('Prepare project','Preparar proyecto'):t('Prepare environment','Preparar entorno')}</button></div>}
          {activeStatuses.includes(item.status)&&<div className="chat-inline-status"><LoaderCircle className="chat-spin" size={14}/> {t(describe(item.status),item.status==='queued'?'Esperando a la IA…':'Preparando cambios…')}</div>}
          {item.status==='failed'&&!item.events?.some(e=>e.kind==='generation_cancelled')&&<RetryContext key={`${item.id}:${item.events?.slice(-1)[0]?.sequence??0}`} item={item} candidates={candidates} ready={inventoryReady} disabled={workingId!==null||busy} dirtyPaths={dirtyPaths} onDecision={(retry,selected)=>generationDecision(item,retry,selected)}/>}

          {workingId===item.id&&item.status!=='failed'&&<div className="chat-inline-status" role="status"><LoaderCircle className="chat-spin" size={14}/> {item.status==='applied'?(jvm?t('Preparing project…','Preparando proyecto…'):t('Preparing Python environment…','Preparando entorno Python…')):item.status==='tested'?t('Applying changes…','Aplicando cambios…'):t('Running approved local tests…','Ejecutando tests locales autorizados…')}</div>}
          {item.id!==approvalItem?.id&&['ready','test_failed'].includes(item.status)&&<button className="chat-link" disabled={workingId!==null} onClick={()=>setSelectedApproval(item.id)}>{t('Review command','Revisar comando')}</button>}
          {item.id===approvalItem?.id&&['ready','test_failed'].includes(item.status)&&workingId!==item.id&&(!skipped.includes(item.id)?<>
            {item.status==='test_failed'&&!infrastructureFailure(item)?<>
              <p className="chat-action-text">{repairCount(item)>=3?t('I could not resolve the failure after three repair attempts. Start a new request to continue.','No he podido resolver el fallo tras tres intentos de corrección. Inicia una nueva petición para continuar.'):t('The tests failed. Shall I correct the proposal before testing again?','Los tests han fallado. ¿Quieres que corrija la propuesta antes de volver a probarla?')}</p>
              <div className="chat-inline-actions"><button className="chat-inline-muted" disabled={workingId!==null} onClick={()=>void defer(item.id,'tests')}>{t('Cancel','Cancelar')}</button>{repairCount(item)<3&&<button className="chat-inline-primary" disabled={workingId!==null} onClick={()=>void repair(item.id)}>{t('Fix and retry','Corregir y reintentar')}</button>}</div>
            </>:<>
              <p className="chat-action-text">{item.status==='test_failed'?t('The runner failed. May I try the command again?','Ha fallado el entorno de ejecución. ¿Puedo volver a ejecutar el comando?'):t('May I run this command to check the changes?','¿Puedo ejecutar este comando para comprobar los cambios?')}</p>
              {testApproval?.id===item.id?<><pre className="chat-history-command">{commandText(testApproval.preview.command)}</pre><small>{t('Temporary copy, local user permissions and Internet access.','Copia temporal, permisos de usuario locales y acceso a Internet.')}{testApproval.preview.command[0]==='uv'&&t(' Python dependencies may be installed in a separate environment.',' Se pueden instalar dependencias Python en un entorno independiente.')}</small><div className="chat-inline-actions"><button className="chat-inline-muted" disabled={workingId!==null} onClick={()=>void defer(item.id,'tests')}>{t('Skip','Omitir')}</button><button className="chat-inline-primary" disabled={workingId!==null} onClick={()=>void approveTests(item.id)}>{t('Allow once','Permitir una vez')}</button></div></>:<p>{t('Preparing command approval…','Preparando autorización…')}</p>}
            </>}
          </>:<div className="chat-inline-status">{item.status==='test_failed'?t('Repair paused.','Corrección detenida.'):t('Tests not authorized.','Tests no autorizados.')} <button className="chat-link" onClick={()=>setSkipped(old=>old.filter(id=>id!==item.id))}>{t('Request again','Solicitar de nuevo')}</button></div>)}
          {item.status==='tested'&&workingId!==item.id&&(discarded.includes(item.id)?<div className="chat-inline-status">{t('Changes not applied.','Cambios no aplicados.')} <button className="chat-link" onClick={()=>setDiscarded(old=>old.filter(id=>id!==item.id))}>{t('Review again','Revisar de nuevo')}</button></div>:<>
            <p className="chat-action-text">{t(`Tests passed. Apply the verified changes to ${projectName}?`,`Los tests han pasado. ¿Aplico los cambios a ${projectName}?`)}{t(' This will write to disk.',' Esto escribirá en disco.')}</p>
            <div className="chat-inline-actions"><button className="chat-inline-muted" disabled={workingId!==null} onClick={()=>void defer(item.id,'apply')}>{t('Not now','Ahora no')}</button><button className="chat-inline-primary" disabled={workingId!==null} onClick={()=>void apply(item.id)}><Check size={13}/> {t('Accept changes','Aceptar cambios')}</button></div>
          </>)}
        </div>
      </div>;})}
      <div ref={bottom}/>
    </div>
    {error&&<div className="chat-error chat-global-error" role="alert"><CircleAlert size={14}/>{error}<button onClick={()=>setError('')}><X size={13}/></button></div>}
    <form className="chat-composer" onSubmit={e=>void submit(e)}>
      {paths.length>0&&<div className="chat-context-tags">{paths.map(path=><span key={path} className={`chat-context-tag ${eligibleActive.includes(path)&&!manual.includes(path)?'automatic':''}`} title={path}><FileCode2 size={13}/><span>{path.split('/').pop()}</span><button type="button" aria-label={`Remove ${path} from context`} disabled={busy} onClick={()=>onExclude(path)}><X size={12}/></button></span>)}</div>}
      {terminalContext.map(t=><div key={t.id} className="chat-terminal-attachment"><details><summary><Terminal size={13}/> {t.name} · Preview output</summary><pre className="chat-test-output">{t.output}</pre></details><button type="button" disabled={busy} aria-label={`Remove ${t.name}`} onClick={()=>onRemoveTerminal(t.id)}><X size={12}/></button></div>)}
      {pickerOpen&&<div className="chat-context-picker"><input aria-label="Search project files" placeholder="Search project files…" value={search} onChange={e=>{if(mention)setDraft(old=>old.slice(0,old.length-mention[1].length)+e.target.value);else setQuery(e.target.value);}} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();if(matches[0])choose(matches[0].path);}if(e.key==='Escape'){setContextOpen(false);if(mention)setDraft(old=>old.slice(0,old.length-mention[0].length));}}}/><div className="chat-context-results">{!mention&&terminalSessions.filter(t=>t.name.toLowerCase().includes(search.toLowerCase())).map(t=><button type="button" key={`terminal-${t.id}`} disabled={busy} onClick={()=>{onAttachTerminal(t.id);setContextOpen(false);}}><Terminal size={14}/><span>{t.name}</span>{terminalContext.some(c=>c.id===t.id)&&<Check size={13}/>}</button>)}{matches.map(c=><button type="button" key={c.path} disabled={busy||(!manual.includes(c.path)&&manual.length>=8)} onClick={()=>choose(c.path)} title={c.path}><FileCode2 size={14}/><span>{c.path}</span>{paths.includes(c.path)&&<Check size={13}/>}</button>)}{!matches.length&&<small>No eligible files found</small>}</div></div>}
      <textarea aria-label="Ask AI" placeholder="Ask AI about your project…" rows={3} value={draft} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Escape'&&pickerOpen){setContextOpen(false);if(mention)setDraft(old=>old.slice(0,old.length-mention[0].length));}if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();if(mention&&matches[0])choose(matches[0].path);else void submit(e);}}}/>
      <div className="chat-composer-bottom"><div className="chat-context-tools"><button type="button" className="chat-add-context" disabled={busy} onClick={()=>{setQuery('');setContextOpen(v=>!v);}}><Paperclip size={14}/> Add context</button></div><button type="submit" aria-label="Send to AI" disabled={!draft.trim()||loading||busy||workingId!==null||!inventoryReady}>{busy?<LoaderCircle className="chat-spin" size={16}/>:<Send size={16}/>}</button></div>
    </form>
  </div>;
}

export default function AIChat(props:Props){
  const [conversations,setConversations]=useState<ChatConversation[]>([]);
  const [active,setActive]=useState<string|null>(null);
  const [pending,setPending]=useState(false);
  const [busy,setBusy]=useState(false);
  const [history,setHistory]=useState(false);
  const [options,setOptions]=useState(false);
  const [error,setError]=useState('');
  const [epoch,setEpoch]=useState(0);
  const current=conversations.find(c=>c.id===active);
  const refresh=async()=>{const result=await listConversations(props.projectId);setConversations(result);return result;};
  useEffect(()=>{let cancelled=false;setPending(true);listConversations(props.projectId).then(result=>{if(!cancelled){setConversations(result);setActive(result[0]?.id??null);}}).catch(e=>{if(!cancelled)setError(String(e));}).finally(()=>{if(!cancelled)setPending(false);});return()=>{cancelled=true;};},[props.projectId]);
  const select=(id:string|null)=>{props.onConversationChange();setBusy(false);setActive(id);setHistory(false);setOptions(false);props.onClearTerminals();};
  const perform=async(action:()=>Promise<void>)=>{if(busy||pending)return;setPending(true);setError('');try{await action();}catch(e){setError(String(e));}finally{setPending(false);}};
  const create=()=>void perform(async()=>{const c=await createConversation(props.projectId);await refresh();if(props.askTerminal&&!active){setActive(c.id);setHistory(false);}else select(c.id);});
  useEffect(()=>{if(props.askTerminal&&!active&&!pending&&!error)create();},[props.askTerminal,active,pending,error]);
  const rename=()=>{if(!current||busy||pending)return;const title=window.prompt('Conversation title',current.title);if(title?.trim())void perform(async()=>{await renameConversation(props.projectId,current.id,title);await refresh();setOptions(false);});};
  const remove=(clear:boolean)=>{if(!current||busy||pending||!window.confirm(clear?'Clear this conversation? Pending proposals will be discarded. Project files will not change.':'Delete this conversation? Pending proposals will be discarded. Project files will not change.'))return;void perform(async()=>{await removeConversation(props.projectId,current.id,clear);const result=await refresh();select(clear?current.id:result[0]?.id??null);setEpoch(n=>n+1);});};
  return <div className="chat-shell">
    <div className="chat-topline"><span className="chat-conversation-title" title={current?.title}>{current?.title??'Conversations'}</span><div className="chat-conversation-tools"><button title="Conversation history" aria-label="Conversation history" onClick={()=>{setHistory(v=>!v);setOptions(false);}}><History size={15}/></button><button title="New conversation" aria-label="New conversation" disabled={busy||pending} onClick={create}><Plus size={16}/></button><button title="Conversation options" aria-label="Conversation options" disabled={!current||busy||pending} onClick={()=>{setOptions(v=>!v);setHistory(false);}}><Ellipsis size={16}/></button></div></div>
    {history&&<div className="chat-conversation-list">{conversations.map(c=><button key={c.id} disabled={busy||pending} className={c.id===active?'selected':''} onClick={()=>select(c.id)}><span>{c.title}</span><small>{chatDay(c.updated_at)}</small></button>)}{!conversations.length&&<small>No conversations yet</small>}</div>}
    {options&&<div className="chat-conversation-list"><button onClick={rename}>Rename conversation</button><button onClick={()=>remove(true)}>Clear conversation</button><button onClick={()=>remove(false)}>Delete conversation</button></div>}
    {error&&<div role="alert" className="chat-error">{error}</div>}
    {active?<ConversationChat key={`${active}:${epoch}`} {...props} conversationId={active} onBusy={setBusy} onSubmitted={()=>{void refresh().catch(e=>setError(String(e)));}}/>:<div className="chat-empty"><Bot size={28}/><h3>Start a conversation</h3><button disabled={pending} onClick={create}>New conversation</button></div>}
  </div>;
}
