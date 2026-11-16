import { useEffect, useRef, useState } from 'react';
import { Bot, Check, ChevronDown, ChevronRight, CircleAlert, FileCode2, LoaderCircle, Paperclip, Send, Terminal, X } from 'lucide-react';
import { applyProposal, createProposal, getProposal, listProposals, testProposal, previewTest, type TestPreview, getRepositoryInsights, previewRepositoryContext, type RepositoryInsights, type ContextPreview, type Proposal, type ProposalChange } from './api';

type Props = { projectId: string; projectName: string; projectKind: 'managed'|'existing'; contextPaths: string[]; contextDigest: string|null; onReview: (proposalId:string, change: ProposalChange)=>void; onApplied: ()=>void; onContext: ()=>void; onApproveContext: (paths:string[], digest:string|null)=>void };
const activeStatuses = ['queued','running'];
const describe = (status: Proposal['status']) => ({queued:'Waiting for the AI…',running:'Preparing changes…',ready:'Changes ready · Approval required',tested:'Tests passed · Ready to review',test_failed:'Tests failed · Review the output',applied:'Changes applied',failed:'Could not prepare changes'})[status];

const needsContext = (error?: string | null) => /Permission required to read and modify|already exists: use modify|Review and approve repository context/i.test(error ?? '');

export default function AIChat({projectId,projectName,projectKind,contextPaths,contextDigest,onReview,onApplied,onApproveContext}:Props) {
  const [items,setItems] = useState<Proposal[]>([]);
  const [draft,setDraft] = useState('');
  const [busy,setBusy] = useState(false);
  const [workingId,setWorkingId] = useState<string|null>(null);
  const [error,setError] = useState('');
  const [skipped,setSkipped] = useState<string[]>([]);
  const [selectedApproval,setSelectedApproval] = useState<string|null>(null);
  const [discarded,setDiscarded] = useState<string[]>([]);
  const [showOutput,setShowOutput] = useState<string|null>(null);
  const [showHistory,setShowHistory] = useState(false);
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
  useEffect(()=>{let cancelled=false;setItems([]);setError('');setInsights(null);setContextOpen(false);setSelected(contextPaths);setPreview(null);setTestApproval(null);setSkipped([]);setDiscarded([]);setSelectedApproval(null);listProposals(projectId).then(result=>{if(!cancelled)setItems(result.reverse());}).catch(e=>{if(!cancelled)setError(String(e));});return()=>{cancelled=true;};},[projectId]);
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
    try{const proposal=await createProposal(projectId,task,contextPaths,contextDigest);setItems(old=>[...old,proposal]);setDraft('');setShowHistory(false);setSelectedApproval(null);window.setTimeout(()=>bottom.current?.scrollIntoView({behavior:'smooth',block:'end'}),50);}
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
      {items.length>1&&<button className="chat-history-toggle" onClick={()=>setShowHistory(v=>!v)}>{showHistory?<ChevronDown size={14}/>:<ChevronRight size={14}/>} {showHistory?'Hide':'Show'} {items.length-1} previous {items.length===2?'task':'tasks'}</button>}
      {items.slice(showHistory?0:-1).map(item=><div className="chat-exchange" key={item.id}>
        <div className="chat-user-bubble">{item.task}</div>
        <div className="chat-assistant-message">
          <div className="chat-response-heading"><Bot size={15}/><strong>{activeStatuses.includes(item.status) && item.agent_stage ? ({analyst:"Analyst · defining acceptance criteria",developer:"Developer · implementing changes",tester:"Tester · reviewing changes",developer_repair:"Developer · fixing failed tests",testing:"Running approved local tests"} as Record<string,string>)[item.agent_stage] || describe(item.status) : item.status==='failed' && needsContext(item.error) ? 'Context authorization required' : describe(item.status)}</strong>{activeStatuses.includes(item.status)&&<LoaderCircle className="chat-spin" size={14}/>}</div>
          {item.error&&<div className={needsContext(item.error)?"chat-error chat-context-required":"chat-error"}><span>{needsContext(item.error) && !item.error.includes('already exists') ? 'This change needs permission to read an existing file. Select it under Context, approve the preview, then retry your request.' : needsContext(item.error) && item.error.includes('already exists') ? 'The AI tried to create a file that already exists. Please approve the existing file in Context and retry.' : item.error}</span>{needsContext(item.error)&&<button type="button" className="chat-secondary-action" onClick={()=>{setDraft(item.task);void openContext();}}>Choose project files</button>}</div>}
          {(item.plan?.acceptance?.length ?? 0) > 0 && (
  <details className="chat-acceptance">
    <summary>
      Acceptance criteria ({item.plan?.acceptance?.length ?? 0})
    </summary>
    <ul>
      {item.plan?.acceptance?.map((criterion, i) => (
        <li key={i}>{criterion}</li>
      ))}
    </ul>
  </details>
)}
          {item.changes.length>0&&<div className="chat-change-card">
            <div className="chat-change-summary"><strong>{item.changes.length} {item.changes.length===1?'file':'files'}</strong><span>Review in editor</span></div>
            {item.changes.map(change=><button key={change.path} className="chat-change-row" onClick={()=>{onReview(item.id,change);}} title="Review diff in editor"><FileCode2 size={14}/><span>{change.path}</span><small>{change.action}</small><ChevronRight size={13}/></button>)}
          </div>}
          {item.status==='tested'&&<div className="chat-test-success"><Check size={14}/> Tests passed</div>}
          {item.status==='test_failed'&&<div className="chat-error"><CircleAlert size={14}/> Tests failed; changes have not been applied</div>}
          {item.status==='applied'&&<div className="chat-test-success"><Check size={14}/> Changes saved to your project</div>}
          {item.test_output&&<><button className="chat-link" onClick={()=>setShowOutput(showOutput===item.id?null:item.id)}>{showOutput===item.id?'Hide':'Show'} test output</button>{showOutput===item.id&&<pre className="chat-test-output">{item.test_output}</pre>}</>}
          {workingId===item.id&&<div className="chat-inline-status" role="status"><LoaderCircle className="chat-spin" size={14}/> {item.status==='tested'?'Applying changes…':'Running approved local tests…'}</div>}
          {item.id!==approvalItem?.id&&['ready','test_failed'].includes(item.status)&&<button className="chat-link" disabled={workingId!==null} onClick={()=>setSelectedApproval(item.id)}>Review command</button>}
          {item.id===approvalItem?.id&&['ready','test_failed'].includes(item.status)&&workingId!==item.id&&(!skipped.includes(item.id)?<>
            <p className="chat-action-text">{item.status==='test_failed'?'I can run the tests again.':'I’d like to run the tests to verify these changes.'}</p>
            <div className="chat-command-card">
              <div className="chat-command-title"><Terminal size={14}/> Run command <small>Local</small></div>
              {testApproval?.id===item.id?<><pre>{testApproval.preview.command.map(arg=>/^[\w./:=+-]+$/.test(arg)?arg:JSON.stringify(arg)).join(' ')}</pre><p>Runs a temporary copy with your user permissions and Internet access. Review the files first.</p><div className="chat-inline-actions"><button className="chat-inline-muted" disabled={workingId!==null} onClick={()=>setSkipped(old=>[...old,item.id])}>Skip</button><button className="chat-inline-primary" disabled={workingId!==null} onClick={()=>void approveTests(item.id)}>Allow once</button></div></>:<><p>Preparing command approval…</p><button className="chat-inline-muted" onClick={()=>setSkipped(old=>[...old,item.id])}>Cancel</button></>}
            </div></>:<div className="chat-inline-status">Tests not authorized. <button className="chat-link" onClick={()=>setSkipped(old=>old.filter(id=>id!==item.id))}>Request again</button></div>)}
          {item.status==='tested'&&workingId!==item.id&&(discarded.includes(item.id)?<div className="chat-inline-status">Changes not applied. <button className="chat-link" onClick={()=>setDiscarded(old=>old.filter(id=>id!==item.id))}>Review again</button></div>:<>
            <p className="chat-action-text">Tests passed. Apply the verified changes to {projectName}?{projectKind==='existing'?' This will write to your registered project.':''}</p>
            <div className="chat-inline-actions"><button className="chat-inline-muted" disabled={workingId!==null} onClick={()=>setDiscarded(old=>[...old,item.id])}>Not now</button><button className="chat-inline-primary" disabled={workingId!==null} onClick={()=>void apply(item.id)}><Check size={13}/> Accept changes</button></div>
          </>)}
        </div>
      </div>)}
      <div ref={bottom}/>
    </div>
    {error&&<div className="chat-error chat-global-error" role="alert"><CircleAlert size={14}/>{error}<button onClick={()=>setError('')}><X size={13}/></button></div>}
    <form className="chat-composer" onSubmit={e=>void submit(e)}>
      <textarea aria-label="Ask AI" placeholder="Ask AI to change your project…" rows={3} value={draft} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void submit(e);}}}/>
      <div className="chat-composer-bottom"><span>Changes require your approval</span><button type="submit" aria-label="Send to AI" disabled={!draft.trim()||busy}>{busy?<LoaderCircle className="chat-spin" size={16}/>:<Send size={16}/>}</button></div>
    </form>
  </div>;
}
