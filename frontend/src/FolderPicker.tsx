import { useEffect, useState } from 'react';
import { ArrowLeft, Check, ChevronRight, Folder, FolderOpen, X } from 'lucide-react';
import { browseLocalDirectories, type FolderListing } from './api';

export default function FolderPicker({ onSelect, onClose }: { onSelect: (path: string) => void; onClose: () => void }) {
  const [listing, setListing] = useState<FolderListing | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  async function navigate(path = '') {
    setLoading(true); setError('');
    try { setListing(await browseLocalDirectories(path)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to browse directories'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void navigate(); }, []);
  return <div className="overlay folder-overlay" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
    <div className="dialog folder-dialog" role="dialog" aria-modal="true" aria-label="Choose project directory">
      <div className="dialog-heading"><div><div className="eyebrow">LOCAL FOLDER BROWSER</div><h2>Choose a project folder</h2><p>Browse directories on the machine running FastAPI. Only folders under the configured browse root are available.</p></div><button className="icon-button" aria-label="Close folder picker" onClick={onClose}><X size={19}/></button></div>
      <div className="folder-current"><FolderOpen size={17}/><span>{listing?.path ?? 'Loading…'}</span></div>
      <div className="folder-list">
        {listing?.parent && <button onClick={() => void navigate(listing.parent!)} disabled={loading}><ArrowLeft size={16}/> Parent directory</button>}
        {listing?.directories.map(folder => <button key={folder.path} onClick={() => void navigate(folder.path)} disabled={loading}><Folder size={16}/><span>{folder.name}</span><ChevronRight size={15}/></button>)}
        {!loading && listing?.directories.length === 0 && <p className="mission-muted">No subfolders here. You can select this directory.</p>}
        {loading && <p className="mission-muted">Loading directories…</p>}
      </div>
      {listing?.truncated && <p className="mission-muted">Showing the first 200 folders.</p>}
      {error && <div role="alert" className="form-error">{error}</div>}
      <div className="dialog-footer"><button className="secondary" onClick={onClose}>Cancel</button><button className="primary" disabled={!listing || loading} onClick={() => listing && onSelect(listing.path)}><Check size={16}/> Select this folder</button></div>
    </div>
  </div>;
}
