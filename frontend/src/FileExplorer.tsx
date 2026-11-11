import { useEffect, useState } from 'react';
import { ChevronRight, FileCode2, Folder, FolderOpen, RefreshCw, Search } from 'lucide-react';
import { listProjectFiles, readProjectFile, searchProjectFiles, type DirectoryListing, type FilePreview, type FileSearchResult } from './api';

function highlightedLine(line: string, language: string) {
  // A lightweight, read-only highlighter. React escapes every text segment.
  const pattern = language === 'python'
    ? /(#.*$|\b(?:def|class|return|if|else|elif|for|while|import|from|as|try|except|with|raise|None|True|False|async|await|pass)\b|\b\d+(?:\.\d+)?\b|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g
    : /(\/\/.*$|\b(?:const|let|var|function|export|import|from|return|if|else|class|interface|type|async|await|true|false|null)\b|\b\d+(?:\.\d+)?\b|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g;
  return line.split(pattern).filter(Boolean).map((part, index) => {
    const kind = part.startsWith('#') || part.startsWith('//') ? 'comment' : /^['"]/.test(part) ? 'string' : /^\d/.test(part) ? 'number' : /^(def|class|return|if|else|elif|for|while|import|from|as|try|except|with|raise|None|True|False|async|await|pass|const|let|var|function|export|interface|type|true|false|null)$/.test(part) ? 'keyword' : '';
    return <span key={index} className={kind ? `syntax-${kind}` : undefined}>{part}</span>;
  });
}

export default function FileExplorer({ projectId }: { projectId: string }) {
  const [folder, setFolder] = useState('');
  const [listing, setListing] = useState<DirectoryListing | null>(null);
  const [preview, setPreview] = useState<FilePreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [version, setVersion] = useState(0);
  const [query, setQuery] = useState('');
  const [searchResult, setSearchResult] = useState<FileSearchResult | null>(null);
  const [searching, setSearching] = useState(false);
  useEffect(() => { setFolder(''); setPreview(null); setListing(null); setError(''); setQuery(''); setSearchResult(null); }, [projectId]);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    void listProjectFiles(projectId, folder).then(data => { if (!cancelled) setListing(data); })
      .catch(err => { if (!cancelled) { setListing(null); setError(err instanceof Error ? err.message : 'Unable to list files'); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [projectId, folder, version]);
  useEffect(() => {
    if (!query.trim()) { setSearchResult(null); setSearching(false); return; }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setSearching(true);
      void searchProjectFiles(projectId, query.trim()).then(result => { if (!cancelled) setSearchResult(result); })
        .catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : 'Search failed'); })
        .finally(() => { if (!cancelled) setSearching(false); });
    }, 300);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [projectId, query]);
  async function openFile(path: string) {
    setError(''); setPreview(null);
    try { setPreview(await readProjectFile(projectId, path)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to preview file'); }
  }
  const crumbs = folder.split('/').filter(Boolean);
  const entries = query.trim() ? searchResult?.entries : listing?.entries;
  const extension = preview?.path.split('.').pop()?.toLowerCase();
  const language = extension === 'py' ? 'python' : ['js', 'jsx', 'ts', 'tsx', 'json'].includes(extension || '') ? 'javascript' : 'plain';
  return <section className="file-explorer">
    <div className="section-heading"><div><h2><FolderOpen size={20}/> Explorer</h2><p>Read-only code viewer · UTF-8 · 256 KiB preview limit</p></div><button className="secondary" onClick={() => { setVersion(v => v + 1); setQuery(''); }}><RefreshCw size={15}/> Refresh</button></div>
    <div className="file-explorer-layout">
      <div className="file-browser">
        <div className="explorer-search"><Search size={16}/><input aria-label="Search files by name" placeholder="Search files by name…" value={query} onChange={e => setQuery(e.target.value)}/></div>
        {!query.trim() && <div className="file-breadcrumb"><button onClick={() => { setFolder(''); setPreview(null); }}>Root</button>{crumbs.map((part, i) => <span key={i}><ChevronRight size={12}/><button onClick={() => { setFolder(crumbs.slice(0, i + 1).join('/')); setPreview(null); }}>{part}</button></span>)}</div>}
        {loading && !query.trim() || searching ? <p className="mission-muted">Loading…</p> : entries?.length ? entries.map(entry => <button key={entry.path} className={`file-entry ${preview?.path === entry.path ? 'file-entry-active' : ''}`} title={entry.path} onClick={() => entry.kind === 'directory' ? (setFolder(entry.path), setPreview(null)) : void openFile(entry.path)}>{entry.kind === 'directory' ? <Folder size={16}/> : <FileCode2 size={16}/>}<span>{query.trim() ? entry.path : entry.name}</span>{entry.kind === 'directory' && <ChevronRight size={14}/>}</button>) : <p className="mission-muted">{query.trim() ? 'No matching files.' : 'No visible files in this directory.'}</p>}
        {(query.trim() ? searchResult?.truncated : listing?.truncated) && <p className="mission-muted">Results truncated. Refine your search.</p>}
      </div>
      <div className="file-preview"><div className="file-preview-header"><span>{preview ? preview.path : 'Select a file to preview'}</span><span>{preview ? `${preview.content.split('\n').length} lines · ${language}` : 'READ ONLY'}</span></div>{preview ? <div className="code-viewer" role="region" aria-label="Read-only source code"><div className="code-lines">{preview.content.split('\n').map((line, i) => <div className="code-line" key={i}><span className="line-number" aria-hidden="true">{i + 1}</span><span className="line-content">{language === 'plain' ? line : highlightedLine(line, language)}</span></div>)}</div></div> : <div className="file-placeholder"><FileCode2 size={30}/><p>Choose a text file from the explorer.</p></div>}</div>
    </div>
    {error && <div className="alert" role="alert">{error}</div>}
  </section>;
}
