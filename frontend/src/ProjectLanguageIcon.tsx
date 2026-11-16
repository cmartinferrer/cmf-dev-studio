import { Folder } from 'lucide-react';
import type { ProjectLanguage } from './api';

/** Local language artwork; unknown or automatic languages retain the folder icon. */
export default function ProjectLanguageIcon({ language, size = 16 }: { language?: ProjectLanguage; size?: number }) {
  const props = { width: size, height: size, viewBox: '0 0 24 24', className: 'project-language-icon', 'aria-hidden': true as const, focusable: false as const };
  switch (language) {
    case 'java':
      return <svg {...props} fill="none" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 1c5 4-5 6-1 10M16 4c-5 3-3 5-1 7" stroke="#f89820" strokeWidth="1.6"/>
        <path d="M5 12c-5 2 10 4 14 0M6 15c-3 2 9 3 12 0M7 18c-2 2 8 3 10 0M3 21c4 2 14 2 19-1M19 13c5-2 5 3 1 4" stroke="#78a9cc" strokeWidth="1.5"/>
      </svg>;
    case 'kotlin':
      return <svg {...props}><path fill="#7f52ff" d="M2 2h20L12 12 22 22H2z"/><path fill="#c85bf0" d="M2 2h20L2 22z"/><path fill="#e448a0" d="M2 2h20L12 12z"/></svg>;
    case 'python':
      return <svg {...props}>
        <path fill="#3776ab" d="M12 1H8C5 1 4 3 4 6v3h9v1H4c-3 0-4 2-4 5s2 5 5 5h2v-4c0-3 2-5 5-5h5c3 0 4-2 4-5V5c0-3-3-4-6-4z"/>
        <path fill="#ffd343" d="M12 23h4c3 0 4-2 4-5v-3h-9v-1h9c3 0 4-2 4-5s-2-5-5-5h-2v4c0 3-2 5-5 5H7c-3 0-4 2-4 5v1c0 3 3 4 6 4z" transform="translate(0 0)"/>
        <circle cx="8" cy="4" r="1.2" fill="white"/><circle cx="16" cy="20" r="1.2" fill="white"/>
      </svg>;
    default:
      return <Folder size={size} className="project-language-icon" aria-hidden="true"/>;
  }
}
