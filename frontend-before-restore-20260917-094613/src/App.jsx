import React from 'react';
import { UrbanPulseProvider, useUrbanPulse } from './context/UrbanPulseContext';
import { Sidebar } from './components/common/Sidebar';
import { Header } from './components/common/Header';
import { NotificationDrawer } from './components/common/NotificationDrawer';
import { CoreWorkspace, CoreReport } from './pages/CoreWorkspace';
function AppContent() {
  const {activeRoute,selectedReport}=useUrbanPulse();
  return <div className="flex h-screen w-screen overflow-hidden bg-background"><Sidebar/><div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden"><Header/>
    <div className="px-6 py-2 text-xs text-amber-800 bg-amber-50 border-b border-amber-100">Prototype: inference runs on this laptop. Recorded inputs use labelled simulated GPS. Congestion is estimated from vehicle counts.</div>
    <main className="flex-1 overflow-y-auto p-6"><div className="max-w-[1600px] mx-auto"><CoreWorkspace key={activeRoute} page={activeRoute}/></div></main>
    </div><CoreReport key={selectedReport?.id || 'closed'}/><NotificationDrawer/></div>;
}
export default function App(){return <UrbanPulseProvider><AppContent/></UrbanPulseProvider>;}
