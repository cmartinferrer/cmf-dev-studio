import { useEffect, useState } from 'react';
import { ChevronRight, FileCode2, Folder, FolderOpen, RefreshCw } from 'lucide-react';
import { listProjectFiles, readProjectFile, type DirectoryListing, type FilePreview } from './api';

export default function FileExplorer({ projectId }: { projectId: string }) {
  const [folder, setFolder] = useState('');
  const [listing, setListing] = useState<DirectoryListing | null>(null);
  const [preview, setPreview] = useState<FilePreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [version, setVersion] = useState(0);
  useEffect(() => { setFolder(''); setPreview(null); setListing(null); setError(''); }, [projectId]);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    void listProjectFiles(projectId, folder).then(data => { if (!cancelled) setListing(data); })
      .catch(err => { if (!cancelled) { setListing(null); setError(err instanceof Error ? err.message : 'Unable to list files'); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [projectId, folder, version]);
  async function openFile(path: string) {
    setError(''); setPreview(null);
    try { setPreview(await readProjectFile(projectId, path)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to preview file'); }
  }
  const crumbs = folder.split('/').filter(Boolean);
  return <section className="file-explorer">
    <div className="section-heading"><div><h2><FolderOpen size={20}/> Project files</h2><p>Read-only explorer · UTF-8 text preview · 256 KiB limit</p></div><button className="secondary" onClick={() => setVersion(v => v + 1)}><RefreshCw size={15}/> Refresh</button></div>
    <div className="file-explorer-layout">
      <div className="file-browser">
        <div className="file-breadcrumb"><button onClick={() => { setFolder(''); setPreview(null); }}>Root</button>{crumbs.map((part, i) => <span key={i}><ChevronRight size={12}/><button onClick={() => { setFolder(crumbs.slice(0, i + 1).join('/')); setPreview(null); }}>{part}</button></span>)}</div>
        {loading ? <p className="mission-muted">Loading…</p> : listing?.entries.length ? listing.entries.map(entry => <button key={entry.path} className="file-entry" onClick={() => entry.kind === 'directory' ? (setFolder(entry.path), setPreview(null)) : void openFile(entry.path)}>{entry.kind === 'directory' ? <Folder size={16}/> : <FileCode2 size={16}/>}<span>{entry.name}</span>{entry.kind === 'directory' && <ChevronRight size={14}/>}</button>) : <p className="mission-muted">No visible files in this directory.</p>}
        {listing?.truncated && <p className="mission-muted">Directory listing truncated.</p>}
      </div>
      <div className="file-preview"><div className="file-preview-header">{preview ? preview.path : 'Select a file to preview'}</div>{preview ? <pre><code>{preview.content}</code></pre> : <div className="file-placeholder"><FileCode2 size={30}/><p>Choose a text file from the explorer.</p></div>}</div>
    </div>
    {error && <div className="alert" role="alert">{error}</div>}
  </section>;
}
