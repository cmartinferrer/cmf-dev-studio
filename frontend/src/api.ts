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
