export type Project = { id: string; name: string; path: string; kind: 'managed' | 'existing'; description: string; created_at: string; read_only: boolean };
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
export const listProjects = () => request<Project[]>('/projects');
export const createProject = (name: string, description: string) => request<Project>('/projects', { method: 'POST', body: JSON.stringify({ name, description }) });
export const registerProject = (path: string, name: string, description: string) => request<Project>('/projects/register', { method: 'POST', body: JSON.stringify({ path, name: name || null, description }) });

export type MissionStatus = 'queued' | 'running' | 'completed' | 'failed';
export type MissionResult = { requirements: string[] | string; code: string; tests: string; feedback: string; attempts: number; history: unknown[] };
export type MissionRun = { id: string; project_id: string; description: string; status: MissionStatus; created_at: string; updated_at: string; result: MissionResult | null; error: string };
export type MissionEvent = { id: number; occurred_at: string; type: string; agent: string | null; attempt: number | null; max_attempts: number | null; status: string | null; passed: number | null; failed: number | null; message: string };
export const listMissions = (projectId: string) => request<MissionRun[]>(`/projects/${encodeURIComponent(projectId)}/missions`);
export const startMission = (projectId: string, description: string, contextPaths: string[] = [], contextDigest: string | null = null) => request<MissionRun>(`/projects/${encodeURIComponent(projectId)}/missions`, { method: 'POST', body: JSON.stringify({ description, context_paths: contextPaths, context_digest: contextDigest }) });
export const getMission = (runId: string) => request<MissionRun>(`/missions/${encodeURIComponent(runId)}`);
export const listMissionEvents = (runId: string) => request<MissionEvent[]>(`/missions/${encodeURIComponent(runId)}/events`);

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
export type Proposal = { id: string; project_id: string; status: 'queued' | 'running' | 'ready' | 'failed' | 'tested' | 'test_failed' | 'applied'; test_output?: string; agent_stage?: string; attempts?: number; plan?: {requirements:string[]; acceptance:string[]}; task: string; created_at: string; error: string; changes: ProposalChange[] };
export const createProposal = (projectId: string, task: string, contextPaths: string[], contextDigest: string | null) => request<Proposal>(`/projects/${encodeURIComponent(projectId)}/proposals`, { method: 'POST', body: JSON.stringify({ task, context_paths: contextPaths, context_digest: contextDigest }) });
export const listProposals = (projectId: string) => request<Proposal[]>(`/projects/${encodeURIComponent(projectId)}/proposals`);
export const getProposal = (proposalId: string) => request<Proposal>(`/proposals/${encodeURIComponent(proposalId)}`);

export const testProposal = (proposalId: string) => request<Proposal>(`/proposals/${encodeURIComponent(proposalId)}/test`, {method: 'POST'});
export const applyProposal = (proposalId: string, confirmation: string, allowExisting: boolean) => request<Proposal>(`/proposals/${encodeURIComponent(proposalId)}/apply`, {method: 'POST', body: JSON.stringify({confirmation, allow_existing: allowExisting})});

export type EditableFile = FilePreview & { sha256: string };
export const openEditableFile = (projectId: string, path: string) => request<EditableFile>(`/projects/${encodeURIComponent(projectId)}/editor/file?path=${encodeURIComponent(path)}`);
export const saveEditableFile = (projectId: string, path: string, content: string, expected_sha256: string | null, create: boolean, authorize_existing: boolean) => request<EditableFile>(`/projects/${encodeURIComponent(projectId)}/editor/file`, {method:'PUT',body:JSON.stringify({path,content,expected_sha256,create,authorize_existing})});
export const deleteEditableFile = (projectId: string, path: string, expected_sha256: string, authorize_existing: boolean) => request<{deleted:boolean}>(`/projects/${encodeURIComponent(projectId)}/editor/file`, {method:'DELETE',body:JSON.stringify({path,expected_sha256,authorize_existing})});

export const previewProposalFile = (proposalId: string, path: string) => request<{path:string;before:string;after:string}>(`/proposals/${encodeURIComponent(proposalId)}/preview?path=${encodeURIComponent(path)}`);
