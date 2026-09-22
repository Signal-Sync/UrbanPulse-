import React from 'react';
import {
  LayoutDashboard,
  Map,
  Bus,
  Cone,
  Activity,
  ShieldAlert,
  FileText,
  Droplets,
  Radio,
  School,
  ListFilter,
  Building2,
  Wrench,
  BarChart3,
  Cpu,
  Video,
  Camera,
  Settings
} from 'lucide-react';
import { useUrbanPulse } from '../../context/UrbanPulseContext';

export function Sidebar() {
  const { activeRoute, setActiveRoute, edgeConnected, centralConnection } = useUrbanPulse();

  const navGroups = [
    { label: 'OVERVIEW', items: [
      { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { id: 'live-city', label: 'GIS Event Map', icon: Map }] },
    { label: 'INTELLIGENCE', items: [
      { id: 'road-intel', label: 'Road Intelligence', icon: Cone },
      { id: 'traffic-intel', label: 'Traffic Intelligence', icon: Activity }] },
    { label: 'REVIEW & SYSTEM', items: [
      { id: 'all-logs', label: 'Event Reports', icon: FileText },
      { id: 'edge-network', label: 'Edge Processing', icon: Cpu },
      { id: 'live-camera', label: 'Inference Evidence', icon: Camera }] }
  ];

  return (
    <aside className="w-60 bg-white text-slate-800 flex flex-col h-screen shrink-0 select-none border-r border-slate-200 shadow-subtle z-20">
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-white font-black text-lg shadow-sm">
            UP
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h1 className="font-extrabold tracking-tight text-slate-900 text-base leading-tight">
                URBANPULSE
              </h1>
              <span className="bg-blue-600 text-white text-[10px] font-black px-1.5 py-0.5 rounded">
                AI
              </span>
            </div>
            <p className="text-[10px] tracking-wider uppercase font-bold text-slate-500 mt-0.5">
              Urban Intelligence Platform
            </p>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-5">
        {navGroups.map(group => (
          <div key={group.label} className="space-y-1">
            <h3 className="text-[11px] font-bold tracking-[0.08em] text-slate-500 uppercase px-3 mb-1.5">
              {group.label}
            </h3>
            <div className="space-y-0.5">
              {group.items.map(item => {
                const Icon = item.icon;
                const isActive = activeRoute === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveRoute(item.id)}
                    className={`relative w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                      isActive
                        ? 'bg-blue-50 text-blue-600 font-semibold shadow-xs'
                        : 'text-slate-700 hover:bg-slate-50 hover:text-slate-900'
                    }`}
                  >
                    {/* 3px Active Indicator on Left */}
                    {isActive && (
                      <span className="absolute left-0 top-1.5 bottom-1.5 w-1 bg-blue-600 rounded-r" />
                    )}

                    <div className="flex items-center gap-2.5">
                      <Icon
                        className={`w-4 h-4 ${
                          isActive ? 'text-blue-600' : 'text-slate-500'
                        }`}
                      />
                      <span>{item.label}</span>
                    </div>

                    {item.badge && (
                      <span className="px-1.5 py-0.5 text-[9px] font-bold rounded bg-red-600 text-white">
                        {item.badge}
                      </span>
                    )}
                    {item.highlight && !isActive && (
                      <span className="w-2 h-2 rounded-full bg-blue-600" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="p-4 border-t border-slate-200 bg-slate-50 text-xs space-y-2">
        <p className="font-semibold text-slate-900">Laptop edge prototype</p>
        <p>Edge service: <b>{edgeConnected ? 'Connected' : 'Offline'}</b></p>
        <p>Central events: <b>{centralConnection}</b></p>
      </div>
    </aside>
  );
}
