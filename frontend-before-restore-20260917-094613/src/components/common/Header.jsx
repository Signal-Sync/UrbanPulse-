import React from 'react';
import { Bell } from 'lucide-react';
import { useUrbanPulse } from '../../context/UrbanPulseContext';
export function Header() {
  const { centralConnection, unreadNotifCount, setIsNotificationOpen } = useUrbanPulse();
  return <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between shrink-0 shadow-subtle">
    <div><p className="text-sm font-bold text-slate-900">Road & Traffic Command</p><p className="text-xs text-slate-500">SIH 26124 · Local AI, geospatial events</p></div>
    <div className="flex items-center gap-4"><span className="text-xs text-slate-500">Central: {centralConnection}</span>
      <button aria-label="Open notifications" onClick={()=>setIsNotificationOpen(true)} className="relative p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"><Bell size={18}/>{unreadNotifCount>0 && <span className="absolute -top-2 -right-2 rounded-full bg-red-600 text-white text-xs px-1.5">{unreadNotifCount}</span>}</button>
    </div>
  </header>;
}
