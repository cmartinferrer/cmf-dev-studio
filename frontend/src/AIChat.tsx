import { useEffect, useRef, useState } from 'react';
import { Bot, Check, ChevronDown, ChevronRight, CircleAlert, FileCode2, LoaderCircle, Paperclip, Play, Send, ShieldCheck, X } from 'lucide-react';
import { applyProposal, createProposal, getProposal, listProposals, testProposal, type Proposal, type ProposalChange } from './api';

type Props = { projectId: string; projectName: string; projectKind: 'managed'|'existing'; contextPaths: string[]; contextDigest: string|null; onReview: (proposalId:string, change: ProposalChange)=>void; onApplied: ()=>void; onContext: ()=>void };
const activeStatuses = ['queued','running'];
const describe = (status: Proposal['status']) => ({queued:'Waiting for the AI…',running:'Preparing changes…',ready:'Changes ready to test',tested:'Tests passed · Ready to review',test_failed:'Tests failed · Review the output',applied:'Changes applied',failed:'Could not prepare changes'})[status];

export default function AIChat({projectId,projectName,projectKind,contextPaths,contextDigest,onReview,onApplied,onContext}:Props) {
  const [items,setItems] = useState<Proposal[]>([]);
  const [draft,setDraft] = useState('');
  const [busy,setBusy] = useState(false);
  const [workingId,setWorkingId] = useState<string|null>(null);
  const [error,setError] = useState('');
  const [confirmation,setConfirmation] = useState<string|null>(null);
  const [confirmName,setConfirmName] = useState('');
  const [allowExisting,setAllowExisting] = useState(false);
  const [showOutput,setShowOutput] = useState<string|null>(null);
  const [showHistory,setShowHistory] = useState(false);
  const bottom = useRef<HTMLDivElement|null>(null);
  const testedIds = useRef(new Set<string>());
  useEffect(()=>{let cancelled=false;setItems([]);setError('');testedIds.current.clear();listProposals(projectId).then(result=>{if(!cancelled)setItems(result.reverse());}).catch(e=>{if(!cancelled)setError(String(e));});return()=>{cancelled=true;};},[projectId]);
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
  // Run tests once for newly generated proposals; old saved proposals remain under manual control.
  useEffect(()=>{
    const next=items.find(item=>item.status==='ready' && testedIds.current.has(item.id) && workingId!==item.id);
    if(!next)return;
    setWorkingId(next.id);
    void testProposal(next.id).then(result=>setItems(old=>old.map(p=>p.id===result.id?result:p))).catch(e=>setError(`Tests could not run: ${String(e)}`)).finally(()=>setWorkingId(null));
  },[items,workingId]);
  async function submit(e:React.FormEvent){
    e.preventDefault();const task=draft.trim();if(!task||busy)return;
    setBusy(true);setError('');
    try{const proposal=await createProposal(projectId,task,contextPaths,contextDigest);testedIds.current.add(proposal.id);setItems(old=>[...old,proposal]);setDraft('');setShowHistory(false);window.setTimeout(()=>bottom.current?.scrollIntoView({behavior:'smooth',block:'end'}),50);}
    catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}
  }
  async function runTests(id:string){setWorkingId(id);setError('');try{const result=await testProposal(id);setItems(old=>old.map(p=>p.id===id?result:p));}catch(e){setError(String(e));}finally{setWorkingId(null);}}
  async function apply(id:string){setWorkingId(id);setError('');try{const result=await applyProposal(id,confirmName,allowExisting);setItems(old=>old.map(p=>p.id===id?result:p));setConfirmation(null);setConfirmName('');setAllowExisting(false);onApplied();}catch(e){setError(String(e));}finally{setWorkingId(null);}}
  return <div className="chat-shell">
    <div className="chat-topline"><span><Bot size={15}/> Your coding assistant</span><button title="Choose files to share with AI" onClick={onContext}><Paperclip size={14}/> Context {contextPaths.length>0?`(${contextPaths.length})`:''}</button></div>
    <div className="chat-scroll">
      {!items.length&&<div className="chat-empty"><Bot size={28}/><h3>What shall we build?</h3><p>Describe a change to your project. I'll prepare the files and run tests in an isolated workspace. Nothing is applied without your approval.</p></div>}
      {items.length>1&&<button className="chat-history-toggle" onClick={()=>setShowHistory(v=>!v)}>{showHistory?<ChevronDown size={14}/>:<ChevronRight size={14}/>} {showHistory?'Hide':'Show'} {items.length-1} previous {items.length===2?'task':'tasks'}</button>}
      {items.slice(showHistory?0:-1).map(item=><div className="chat-exchange" key={item.id}>
        <div className="chat-user-bubble">{item.task}</div>
        <div className="chat-assistant-message">
          <div className="chat-response-heading"><Bot size={15}/><strong>{describe(item.status)}</strong>{activeStatuses.includes(item.status)&&<LoaderCircle className="chat-spin" size={14}/>}</div>
          {item.error&&<div className="chat-error">{item.error.includes('Permission required') || item.error.includes('unapproved') ? 'This change needs permission to read an existing file. Select it under Context, approve the preview, then retry your request.' : item.error.includes('Cannot create existing file') || item.error.includes('already exists') ? 'The AI tried to create a file that already exists. Please approve the existing file in Context and retry.' : item.error}<div>{(item.error.includes('Permission') || item.error.includes('unapproved') || item.error.includes('already exists'))&&<button type="button" className="chat-secondary-action" onClick={onContext}>Choose project files</button>}</div></div>}
          {item.changes.length>0&&<div className="chat-change-card">
            <div className="chat-change-summary"><strong>{item.changes.length} {item.changes.length===1?'file':'files'}</strong><span>Review in editor</span></div>
            {item.changes.map(change=><button key={change.path} className="chat-change-row" onClick={()=>{onReview(item.id,change);}} title="Review diff in editor"><FileCode2 size={14}/><span>{change.path}</span><small>{change.action}</small><ChevronRight size={13}/></button>)}
            {item.status==='tested'&&<div className="chat-test-success"><Check size={14}/> Tests passed</div>}
            {item.status==='test_failed'&&<div className="chat-error"><CircleAlert size={14}/> Tests failed; changes have not been applied</div>}
            {item.status==='applied'&&<div className="chat-test-success"><Check size={14}/> Changes saved to your project</div>}
            {item.test_output&&<><button className="chat-link" onClick={()=>setShowOutput(showOutput===item.id?null:item.id)}>{showOutput===item.id?'Hide':'Show'} test output</button>{showOutput===item.id&&<pre className="chat-test-output">{item.test_output}</pre>}</>}
            {['ready','test_failed'].includes(item.status)&&<button className="chat-secondary-action" disabled={workingId!==null} onClick={()=>void runTests(item.id)}><Play size={13}/> {workingId===item.id?'Running tests…':item.status==='test_failed'?'Run tests again':'Run tests'}</button>}
            {item.status==='tested'&&<button className="chat-accept" disabled={workingId!==null} onClick={()=>{setConfirmation(item.id);setConfirmName('');setAllowExisting(false);}}> <ShieldCheck size={14}/> Accept changes</button>}
          </div>}
        </div>
      </div>)}
      <div ref={bottom}/>
    </div>
    {error&&<div className="chat-error chat-global-error" role="alert"><CircleAlert size={14}/>{error}<button onClick={()=>setError('')}><X size={13}/></button></div>}
    <form className="chat-composer" onSubmit={e=>void submit(e)}>
      <textarea aria-label="Ask AI" placeholder="Ask AI to change your project…" rows={3} value={draft} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void submit(e);}}}/>
      <div className="chat-composer-bottom"><span>Changes require your approval</span><button type="submit" aria-label="Send to AI" disabled={!draft.trim()||busy}>{busy?<LoaderCircle className="chat-spin" size={16}/>:<Send size={16}/>}</button></div>
    </form>
    {confirmation!==null&&<div className="chat-modal-backdrop" role="presentation"><div className="chat-modal" role="dialog" aria-modal="true" aria-label="Confirm applying changes"><h3>Apply changes to {projectName}?</h3><p>The tested files will be written to your project. Type the project name to confirm.</p><input aria-label="Exact project name" placeholder={projectName} value={confirmName} onChange={e=>setConfirmName(e.target.value)}/>{projectKind==='existing'&&<label><input type="checkbox" checked={allowExisting} onChange={e=>setAllowExisting(e.target.checked)}/> I authorize changes to this registered project</label>}<div className="chat-modal-actions"><button onClick={()=>setConfirmation(null)}>Cancel</button><button className="chat-accept" disabled={workingId!==null||confirmName!==projectName||(projectKind==='existing'&&!allowExisting)} onClick={()=>void apply(confirmation)}>Apply changes</button></div></div></div>}
  </div>;
}
