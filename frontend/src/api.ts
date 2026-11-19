import type { TerminalContext } from './terminalContext';
export type ProjectLanguage = 'auto' | 'python' | 'java' | 'kotlin';
export const projectLanguageLabels: Record<ProjectLanguage, string> = { auto: 'Auto', python: 'Python', java: 'Java', kotlin: 'Kotlin' };
export type Project = { id: string; name: string; path: string; description: string; created_at: string; language: ProjectLanguage };
export async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(`/api${endpoint}`, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } }); }
  catch { throw new Error('Cannot connect to FastAPI. Is the backend running on port 8000?'); }
  if (!response.ok) {
    const body: { detail?: string | { msg?: string }[] } = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.map(item => item.msg).join('; ') : body.detail;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}
export const updateProjectLanguage = (projectId: string, language: ProjectLanguage) => request<Project>(`/projects/${encodeURIComponent(projectId)}/language`, { method: 'PATCH', body: JSON.stringify({ language }) });
export const listProjects = () => request<Project[]>('/projects');
export const createProject = (name: string, description: string, language: ProjectLanguage, location: string) => request<Project>('/projects', { method: 'POST', body: JSON.stringify({ name, description, language, location }) });
export const registerProject = (path: string) => request<Project>('/projects/register', { method: 'POST', body: JSON.stringify({ path }) });


export type FileEntry = { name: string; path: string; kind: 'file' | 'directory' };
export type DirectoryListing = { path: string; entries: FileEntry[]; truncated: boolean };
export type FilePreview = { path: string; content: string; size: number };
export const listProjectFiles = (projectId: string, path = '') => request<DirectoryListing>(`/projects/${encodeURIComponent(projectId)}/files?path=${encodeURIComponent(path)}`);
export const readProjectFile = (projectId: string, path: string) => request<FilePreview>(`/projects/${encodeURIComponent(projectId)}/file?path=${encodeURIComponent(path)}`);

export type FolderListing = { root: string; path: string; parent: string | null; directories: { name: string; path: string }[]; truncated: boolean };
export const browseLocalDirectories = (path = '') => request<FolderListing>(`/local/directories?path=${encodeURIComponent(path)}`);

export type RepositoryInsights = { technologies: string[]; languages: Record<string, number>; candidates: { path: string; size: number }[]; truncated: boolean; visited: number; limits: { max_files: number; max_file_bytes: number; max_total_bytes: number } };
export type ContextPreview = { files: { path: string; content: string; size: number }[]; total_bytes: number; digest: string };
export const getRepositoryInsights = (projectId: string) => request<RepositoryInsights>(`/projects/${encodeURIComponent(projectId)}/insights`);
export const previewRepositoryContext = (projectId: string, paths: string[]) => request<ContextPreview>(`/projects/${encodeURIComponent(projectId)}/context/preview`, { method: 'POST', body: JSON.stringify({ paths }) });

export type ProposalChange = { action: 'create' | 'modify' | 'delete'; path: string; diff: string; before_sha256: string | null; size: number };
export type ProposalEvent = { sequence:number; kind:string; created_at:string; details:{message?:string; action?:string; query?:string; environment?:string; command?:string[]; output?:string; count?:number; stage?:string; error?:string; context_paths?:string[]; context_changed?:boolean; repair_cancelled?:boolean; critical?:boolean} };
export type Proposal = { assistant_language?:string; terminal_context?: TerminalContext[]; events?: ProposalEvent[]; approved_paths?: string[]; id: string; project_id: string; status: 'queued' | 'running' | 'awaiting_exploration' | 'answered' | 'ready' | 'failed' | 'tested' | 'test_failed' | 'applied'; test_output?: string; agent_stage?: string; attempts?: number; plan?: {requirements:string[]; acceptance:string[]}; task: string; created_at: string; error: string; changes: ProposalChange[] };
export const createProposal = (projectId: string, task: string, contextPaths: string[], contextDigest: string | null, terminalContext:TerminalContext[] = [], assistantLanguage = "English", conversationId?:string) => request<Proposal>(`/projects/${encodeURIComponent(projectId)}/proposals`, { method: 'POST', body: JSON.stringify({ task, context_paths: contextPaths, context_digest: contextDigest, terminal_context: terminalContext, assistant_language: assistantLanguage, conversation_id:conversationId }) });
export const listProposals = (projectId: string, conversationId?:string) => request<Proposal[]>(`/projects/${encodeURIComponent(projectId)}/proposals${conversationId?`?conversation_id=${encodeURIComponent(conversationId)}`:''}`);
export type ChatConversation = {id:string;project_id:string;title:string;created_at:string;updated_at:string};
const conversationsPath=(projectId:string)=>`/projects/${encodeURIComponent(projectId)}/conversations`;
export const listConversations=(projectId:string)=>request<ChatConversation[]>(conversationsPath(projectId));
export const createConversation=(projectId:string)=>request<ChatConversation>(conversationsPath(projectId),{method:'POST'});
export const renameConversation=(projectId:string,id:string,title:string)=>request<ChatConversation>(`${conversationsPath(projectId)}/${encodeURIComponent(id)}`,{method:'PATCH',body:JSON.stringify({title})});
export const removeConversation=(projectId:string,id:string,clear:boolean)=>request<{deleted:boolean}>(`${conversationsPath(projectId)}/${encodeURIComponent(id)}?confirmed=true&clear=${clear}`,{method:'DELETE'});
export const getProposal = (proposalId: string) => request<Proposal>(`/proposals/${encodeURIComponent(proposalId)}`);

export type TestPreview = {command: string[]; approval: string; working_directory: string; timeout: number};
export const previewTest = (proposalId: string) => request<TestPreview>(`/proposals/${encodeURIComponent(proposalId)}/test`);
export const testProposal = (proposalId: string, approval: string) => request<Proposal>(`/proposals/${encodeURIComponent(proposalId)}/test`, {method: 'POST', body: JSON.stringify({approval})});
export const applyProposal = (proposalId: string) => request<Proposal>(`/proposals/${encodeURIComponent(proposalId)}/apply`, {method: 'POST', body: JSON.stringify({approved: true})});

export type EditableFile = FilePreview & { sha256: string };
export const openEditableFile = (projectId: string, path: string) => request<EditableFile>(`/projects/${encodeURIComponent(projectId)}/editor/file?path=${encodeURIComponent(path)}`);
export const saveEditableFile = (projectId: string, path: string, content: string, expected_sha256: string | null, create: boolean) => request<EditableFile>(`/projects/${encodeURIComponent(projectId)}/editor/file`, {method:'PUT',body:JSON.stringify({path,content,expected_sha256,create})});
export const deleteEditableFile = (projectId: string, path: string, expected_sha256: string) => request<{deleted:boolean}>(`/projects/${encodeURIComponent(projectId)}/editor/file`, {method:'DELETE',body:JSON.stringify({path,expected_sha256})});

export const previewProposalFile = (proposalId: string, path: string) => request<{path:string;before:string;after:string}>(`/proposals/${encodeURIComponent(proposalId)}/preview?path=${encodeURIComponent(path)}`);

export const deferProposal = (id:string, action:"tests"|"apply") => request<Proposal>(`/proposals/${encodeURIComponent(id)}/defer`, {method:"POST",body:JSON.stringify({action})});

export const repairProposal = (id:string) => request<Proposal>(`/proposals/${encodeURIComponent(id)}/repair`, {method:"POST"});

export const renameProject = (id:string, name:string) => request<Project>(`/projects/${encodeURIComponent(id)}/name`, {method:'PATCH',body:JSON.stringify({name})});
export const removeProject = (id:string, fromDisk=false) => request<{deleted:boolean}>(`/projects/${encodeURIComponent(id)}?confirmed=true&from_disk=${fromDisk}`, {method:'DELETE'});
export const renameEntry = (id:string,path:string,name:string) => request<{path:string}>(`/projects/${encodeURIComponent(id)}/editor/entry`, {method:'PATCH',body:JSON.stringify({path,name})});
export const removeEntry = (id:string,path:string) => request<{deleted:boolean}>(`/projects/${encodeURIComponent(id)}/editor/entry`, {method:'DELETE',body:JSON.stringify({path,confirmed:true})});

export const decideGeneration = (id:string, retry:boolean, contextPaths?:string[], contextDigest?:string|null) => request<Proposal>(`/proposals/${encodeURIComponent(id)}/generation-decision`, {method:"POST",body:JSON.stringify({retry,context_paths:contextPaths,context_digest:contextDigest})});
export const createDirectory = (id:string,path:string) => request<{path:string}>(`/projects/${encodeURIComponent(id)}/editor/directory`, {method:'POST',body:JSON.stringify({path})});
export const moveEntry = (id:string,path:string,parent:string) => request<{path:string}>(`/projects/${encodeURIComponent(id)}/editor/move`, {method:'PATCH',body:JSON.stringify({path,parent})});
export const batchEntries = (id:string,paths:string[],parent:string|null) => request<{completed:{source:string;path:string}[];error:string|null}>(`/projects/${encodeURIComponent(id)}/editor/batch`, {method:'POST',body:JSON.stringify({paths,parent,confirmed:parent===null})});

export const copyEntries = (id:string,paths:string[],parent:string) => request<{completed:{source:string;path:string}[];error:string|null}>(`/projects/${encodeURIComponent(id)}/editor/copy`, {method:'POST',body:JSON.stringify({paths,parent})});

export type PythonEnvironment = { supported: boolean; path: string | null; version: string | null; source: 'selected' | 'detected' | 'none'; available: boolean; venv_exists: boolean; uv_available: boolean };
export const getPythonEnvironment = (id: string) => request<PythonEnvironment>(`/projects/${encodeURIComponent(id)}/python-environment`);
export const updatePythonEnvironment = (id: string, action: 'create' | 'select' | 'reset', path?: string) => request<PythonEnvironment>(`/projects/${encodeURIComponent(id)}/python-environment`, { method: 'POST', body: JSON.stringify({ action, path, confirmed: true }) });

export const prepareProposalPython = (id: string, confirmed: boolean) => request<Proposal>(`/proposals/${encodeURIComponent(id)}/prepare-python`, {method:'POST', body:JSON.stringify({confirmed})});

export type Jdk = { path: string; version: string };
export type JdkEnvironment = { supported: boolean; current: Jdk | null; available: Jdk[]; source: 'selected' | 'detected' | 'none' };
export const getJdk = (id: string) => request<JdkEnvironment>(`/projects/${encodeURIComponent(id)}/jdk`);
export const updateJdk = (id: string, path: string | null) => request<JdkEnvironment>(`/projects/${encodeURIComponent(id)}/jdk`, { method: 'POST', body: JSON.stringify({ path }) });

export const decideExploration = (id:string, allow:boolean) => request<Proposal>(`/proposals/${encodeURIComponent(id)}/exploration-decision`, {method:"POST",body:JSON.stringify({allow})});

const workspaceSession = crypto.randomUUID();
export const projectPresence = (id:string) => new WebSocket(`${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/projects/${encodeURIComponent(id)}/presence?session=${workspaceSession}`);
export const setProjectOpen = (id:string, open:boolean) => request(`/projects/${encodeURIComponent(id)}/${open?"open":"close"}?session=${workspaceSession}`, {method:"POST", keepalive: !open});
export const getProject = (id:string) => request<Project>(`/projects/${encodeURIComponent(id)}`);
