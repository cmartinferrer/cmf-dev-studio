export type ProjectLanguage = 'auto' | 'python' | 'java' | 'kotlin';
export const projectLanguageLabels: Record<ProjectLanguage, string> = { auto: 'Auto', python: 'Python', java: 'Java', kotlin: 'Kotlin' };
export type Project = { id: string; name: string; path: string; kind: 'managed' | 'existing'; description: string; created_at: string; read_only: boolean; language: ProjectLanguage };
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
export const createProject = (name: string, description: string, language: ProjectLanguage) => request<Project>('/projects', { method: 'POST', body: JSON.stringify({ name, description, language }) });
export const registerProject = (path: string, name: string, description: string) => request<Project>('/projects/register', { method: 'POST', body: JSON.stringify({ path, name: name || null, description }) });


export type FileEntry = { name: string; path: string; kind: 'file' | 'directory' };
export type DirectoryListing = { path: string; entries: FileEntry[]; truncated: boolean };
export type FilePreview = { path: string; content: string; size: number };
export const listProjectFiles = (projectId: string, path = '') => request<DirectoryListing>(`/projects/${encodeURIComponent(projectId)}/files?path=${encodeURIComponent(path)}`);
export const readProjectFile = (projectId: string, path: string) => request<FilePreview>(`/projects/${encodeURIComponent(projectId)}/file?path=${encodeURIComponent(path)}`);

export type FolderListing = { root: string; path: string; parent: string | null; directories: { name: string; path: string }[]; truncated: boolean };
export const browseLocalDirectories = (path = '') => request<FolderListing>(`/local/directories?path=${encodeURIComponent(path)}`);
export type FileSearchResult = { query: string; entries: FileEntry[]; truncated: boolean };
export const searchProjectFiles = (projectId: string, query: string) => request<FileSearchResult>(`/projects/${encodeURIComponent(projectId)}/search?q=${encodeURIComponent(query)}`);

export type RepositoryInsights = { technologies: string[]; languages: Record<string, number>; candidates: { path: string; size: number }[]; truncated: boolean; visited: number; limits: { max_files: number; max_file_bytes: number; max_total_bytes: number } };
export type ContextPreview = { files: { path: string; content: string; size: number }[]; total_bytes: number; digest: string };
export const getRepositoryInsights = (projectId: string) => request<RepositoryInsights>(`/projects/${encodeURIComponent(projectId)}/insights`);
export const previewRepositoryContext = (projectId: string, paths: string[]) => request<ContextPreview>(`/projects/${encodeURIComponent(projectId)}/context/preview`, { method: 'POST', body: JSON.stringify({ paths }) });

export type ProposalChange = { action: 'create' | 'modify' | 'delete'; path: string; diff: string; before_sha256: string | null; size: number };
export type ProposalEvent = { sequence:number; kind:string; created_at:string; details:{command?:string[]; output?:string; count?:number; stage?:string; error?:string; context_paths?:string[]; context_changed?:boolean; repair_cancelled?:boolean} };
export type Proposal = { events?: ProposalEvent[]; approved_paths?: string[]; id: string; project_id: string; status: 'queued' | 'running' | 'ready' | 'failed' | 'tested' | 'test_failed' | 'applied'; test_output?: string; agent_stage?: string; attempts?: number; plan?: {requirements:string[]; acceptance:string[]}; task: string; created_at: string; error: string; changes: ProposalChange[] };
export const createProposal = (projectId: string, task: string, contextPaths: string[], contextDigest: string | null) => request<Proposal>(`/projects/${encodeURIComponent(projectId)}/proposals`, { method: 'POST', body: JSON.stringify({ task, context_paths: contextPaths, context_digest: contextDigest }) });
export const listProposals = (projectId: string) => request<Proposal[]>(`/projects/${encodeURIComponent(projectId)}/proposals`);
export const getProposal = (proposalId: string) => request<Proposal>(`/proposals/${encodeURIComponent(proposalId)}`);

export type TestPreview = {command: string[]; approval: string; working_directory: string; timeout: number};
export const previewTest = (proposalId: string) => request<TestPreview>(`/proposals/${encodeURIComponent(proposalId)}/test`);
export const testProposal = (proposalId: string, approval: string) => request<Proposal>(`/proposals/${encodeURIComponent(proposalId)}/test`, {method: 'POST', body: JSON.stringify({approval})});
export const applyProposal = (proposalId: string, allowExisting: boolean) => request<Proposal>(`/proposals/${encodeURIComponent(proposalId)}/apply`, {method: 'POST', body: JSON.stringify({approved: true, allow_existing: allowExisting})});

export type EditableFile = FilePreview & { sha256: string };
export const openEditableFile = (projectId: string, path: string) => request<EditableFile>(`/projects/${encodeURIComponent(projectId)}/editor/file?path=${encodeURIComponent(path)}`);
export const saveEditableFile = (projectId: string, path: string, content: string, expected_sha256: string | null, create: boolean, authorize_existing: boolean) => request<EditableFile>(`/projects/${encodeURIComponent(projectId)}/editor/file`, {method:'PUT',body:JSON.stringify({path,content,expected_sha256,create,authorize_existing})});
export const deleteEditableFile = (projectId: string, path: string, expected_sha256: string, authorize_existing: boolean) => request<{deleted:boolean}>(`/projects/${encodeURIComponent(projectId)}/editor/file`, {method:'DELETE',body:JSON.stringify({path,expected_sha256,authorize_existing})});

export const previewProposalFile = (proposalId: string, path: string) => request<{path:string;before:string;after:string}>(`/proposals/${encodeURIComponent(proposalId)}/preview?path=${encodeURIComponent(path)}`);

export const deferProposal = (id:string, action:"tests"|"apply") => request<Proposal>(`/proposals/${encodeURIComponent(id)}/defer`, {method:"POST",body:JSON.stringify({action})});

export const repairProposal = (id:string) => request<Proposal>(`/proposals/${encodeURIComponent(id)}/repair`, {method:"POST"});

export const renameProject = (id:string, name:string) => request<Project>(`/projects/${encodeURIComponent(id)}/name`, {method:'PATCH',body:JSON.stringify({name})});
export const removeProject = (id:string) => request<{deleted:boolean}>(`/projects/${encodeURIComponent(id)}?confirmed=true`, {method:'DELETE'});
export const renameEntry = (id:string,path:string,name:string,authorize_existing:boolean) => request<{path:string}>(`/projects/${encodeURIComponent(id)}/editor/entry`, {method:'PATCH',body:JSON.stringify({path,name,authorize_existing})});
export const removeEntry = (id:string,path:string,authorize_existing:boolean) => request<{deleted:boolean}>(`/projects/${encodeURIComponent(id)}/editor/entry`, {method:'DELETE',body:JSON.stringify({path,authorize_existing,confirmed:true})});

export const decideGeneration = (id:string, retry:boolean, contextPaths?:string[], contextDigest?:string|null) => request<Proposal>(`/proposals/${encodeURIComponent(id)}/generation-decision`, {method:"POST",body:JSON.stringify({retry,context_paths:contextPaths,context_digest:contextDigest})});
