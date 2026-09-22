import React, { useState } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  ExternalLink,
  Car,
  Clock,
  CheckCircle2,
  Check,
  UserPlus,
  Play,
  Wrench,
  Lock
} from 'lucide-react';

import { StatCard } from '../components/common/StatCard';
import { StatusBadge } from '../components/common/StatusBadge';
import { HitAndRunWorkflow } from '../components/incident/HitAndRunWorkflow';
import { useUrbanPulse } from '../context/UrbanPulseContext';
import { INITIAL_INCIDENTS } from '../data/incidentsData';

const WORKFLOW_STEPS = [
  {
    status: 'DETECTED',
    label: 'VERIFY',
    icon: Check
  },
  {
    status: 'VERIFIED',
    label: 'ASSIGN',
    icon: UserPlus
  },
  {
    status: 'ASSIGNED',
    label: 'START WORK',
    icon: Play
  },
  {
    status: 'IN PROGRESS',
    label: 'RESOLVE',
    icon: Wrench
  },
  {
    status: 'RESOLVED',
    label: 'VERIFY CLOSE',
    icon: Lock
  }
];

function getNextAction(status) {
  const actions = {
    DETECTED: {
      label: 'VERIFY',
      nextStatus: 'VERIFIED',
      icon: Check
    },

    VERIFIED: {
      label: 'ASSIGN',
      nextStatus: 'ASSIGNED',
      icon: UserPlus
    },

    ASSIGNED: {
      label: 'START WORK',
      nextStatus: 'IN PROGRESS',
      icon: Play
    },

    'IN PROGRESS': {
      label: 'RESOLVE',
      nextStatus: 'RESOLVED',
      icon: Wrench
    },

    RESOLVED: {
      label: 'VERIFY CLOSE',
      nextStatus: 'VERIFIED CLOSED',
      icon: Lock
    }
  };

  return actions[status] || null;
}

export function IncidentCenterPage() {
  const {
    incidents,
    setSelectedReport,
    updateReportStatus
  } = useUrbanPulse();

  const [selectedIncident] = useState(INITIAL_INCIDENTS[0]);

  const handleWorkflowAction = (item) => {
    const action = getNextAction(item.status || 'DETECTED');

    if (!action) {
      return;
    }

    updateReportStatus(
      item.id,
      action.nextStatus,
      `${action.label} action completed from Incident Center.`
    );
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-150">

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-extrabold tracking-tight text-slate-900 flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-red-600" />

            <span>
              Emergency Incident Center & ANPR Crime Investigation
            </span>
          </h1>

          <p className="text-xs text-slate-500">
            AI collision detection, fleeing vehicle deep-tracking,
            optical license plate extraction, and police broadcasts
          </p>
        </div>

        <span className="font-mono text-xs font-bold text-red-700 bg-red-50 border border-red-200 px-3 py-1 rounded-full">
          POLICE ITMS DIRECT BRIDGE ONLINE
        </span>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">

        <StatCard
          title="HIT & RUN INCIDENTS"
          value="1"
          subtitle="ANPR Locked (TN-09-CB-4491)"
          variant="danger"
          badgeText="ACTIVE"
          icon={AlertTriangle}
        />

        <StatCard
          title="RASH DRIVING DETECTIONS"
          value="14"
          subtitle="Speed > 85 km/h in urban zone"
          variant="warning"
          icon={Car}
        />

        <StatCard
          title="PEDESTRIAN NEAR-MISS"
          value="6"
          subtitle="Blind curve & crosswalks"
          variant="default"
          icon={Clock}
        />

        <StatCard
          title="RESOLVED CASES"
          value="9"
          subtitle="Interception completed"
          variant="success"
          icon={CheckCircle2}
        />

      </div>

      {/* Hit-and-Run Pipeline */}
      <HitAndRunWorkflow incident={selectedIncident} />

      {/* Incident Workflow Registry */}
      <div className="bg-white rounded-card border border-slate-200 p-5 shadow-subtle space-y-4">

        <div className="flex items-center justify-between">

          <div>
            <h3 className="font-extrabold text-xs uppercase tracking-wider text-slate-900">
              Incident Workflow Registry
            </h3>

            <p className="text-[11px] text-slate-500 mt-1">
              Every incident follows the controlled municipal response lifecycle.
            </p>
          </div>

          <div className="text-[10px] font-mono font-bold text-slate-500">
            CONTROLLED WORKFLOW
          </div>

        </div>

        {/* Workflow stages */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-2">

          {[
            'DETECTED',
            'VERIFIED',
            'ASSIGNED',
            'IN PROGRESS',
            'RESOLVED',
            'VERIFIED CLOSED'
          ].map((stage, index) => (

            <div
              key={stage}
              className="relative bg-slate-50 border border-slate-200 rounded-lg p-3"
            >
              <div className="text-[9px] font-mono font-bold text-slate-400">
                STEP {index + 1}
              </div>

              <div className="text-[10px] font-extrabold text-slate-800 mt-1">
                {stage}
              </div>

              {index < 5 && (
                <div className="hidden md:block absolute top-1/2 -right-2 text-slate-300 z-10">
                  →
                </div>
              )}
            </div>

          ))}

        </div>

      </div>

      {/* Incident Archive Table */}
      <div className="bg-white rounded-card border border-slate-200 p-5 shadow-subtle space-y-4">

        <div className="flex items-center justify-between">

          <div>
            <h3 className="font-extrabold text-xs uppercase tracking-wider text-slate-900">
              Critical Incident Registry & Police Dispatch Log
            </h3>

            <p className="text-[11px] text-slate-500 mt-1">
              Action buttons are enabled only for the current workflow stage.
            </p>
          </div>

          <div className="text-[10px] font-bold text-slate-500">
            {incidents.length} INCIDENTS
          </div>

        </div>

        <div className="overflow-x-auto">

          <table className="w-full text-left text-xs border-collapse">

            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 font-bold uppercase tracking-wider text-[10px]">

                <th className="py-2.5 px-3">
                  INCIDENT ID
                </th>

                <th className="py-2.5 px-3">
                  CRIME / EVENT TYPE
                </th>

                <th className="py-2.5 px-3">
                  LOCATION
                </th>

                <th className="py-2.5 px-3">
                  SUSPECT VEHICLE
                </th>

                <th className="py-2.5 px-3">
                  OCR NUMBER PLATE
                </th>

                <th className="py-2.5 px-3">
                  BUS & CAM
                </th>

                <th className="py-2.5 px-3">
                  CONFIDENCE
                </th>

                <th className="py-2.5 px-3">
                  STATUS
                </th>

                <th className="py-2.5 px-3 text-right">
                  ACTION
                </th>

              </tr>
            </thead>

            <tbody className="divide-y divide-slate-200">

              {incidents.map(item => {

                const currentStatus =
                  item.status || 'DETECTED';

                const action =
                  getNextAction(currentStatus);

                const ActionIcon =
                  action?.icon || Check;

                return (
                  <tr
                    key={item.id}
                    onClick={() => setSelectedReport(item)}
                    className="cursor-pointer hover:bg-slate-50 transition-colors"
                  >

                    <td className="py-3 px-3 font-mono font-bold text-red-600">
                      {item.id}
                    </td>

                    <td className="py-3 px-3 font-bold text-slate-900 uppercase text-xs">
                      {item.type?.replace(/_/g, ' ')}
                    </td>

                    <td className="py-3 px-3 text-slate-500 max-w-[160px] truncate">
                      {item.location}
                    </td>

                    <td className="py-3 px-3 text-slate-800 text-[11px]">
                      {item.vehicleDetails?.vehicleType ||
                        'Motor Vehicle'}
                    </td>

                    <td className="py-3 px-3">
                      <span className="font-mono font-bold text-slate-900 bg-yellow-300 px-2 py-0.5 rounded border border-yellow-500 inline-block my-0.5 text-[11px] shadow-xs">
                        {item.edgeEvent ? 'Not performed' : (item.vehicleDetails?.numberPlate || item.numberPlate || 'SAMPLE WORKFLOW')}
                      </span>
                    </td>

                    <td className="py-3 px-3 font-mono text-[11px] text-blue-600 font-bold">
                      {item.busId}
                    </td>

                    <td className="py-3 px-3">
                      <span className="font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-100 text-[11px]">
                        {Number.isFinite(item.confidence) ? `${Math.round(item.confidence * 100)}%` : 'Rule-based'}
                      </span>
                    </td>

                    <td className="py-3 px-3">
                      <StatusBadge
                        status={currentStatus}
                        size="xs"
                      />
                    </td>

                    <td
                      className="py-3 px-3"
                      onClick={e => e.stopPropagation()}
                    >

                      <div className="flex items-center justify-end gap-2">

                        <button
                          onClick={() =>
                            setSelectedReport(item)
                          }
                          className="text-[10px] text-blue-600 font-bold hover:underline flex items-center gap-1"
                        >
                          <span>EXAMINE</span>

                          <ExternalLink className="w-3 h-3" />
                        </button>

                        {action && (
                          <button
                            onClick={() =>
                              handleWorkflowAction(item)
                            }
                            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-slate-900 text-white text-[10px] font-extrabold hover:bg-slate-700 transition-colors"
                          >
                            <ActionIcon className="w-3 h-3" />

                            {action.label}
                          </button>
                        )}

                        {!action && (
                          <span className="text-[10px] font-bold text-green-600 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" />
                            CLOSED
                          </span>
                        )}

                      </div>

                    </td>

                  </tr>
                );
              })}

              {incidents.length === 0 && (
                <tr>
                  <td
                    colSpan="9"
                    className="py-10 text-center text-xs text-slate-400"
                  >
                    No active incidents available.
                  </td>
                </tr>
              )}

            </tbody>

          </table>

        </div>

      </div>

    </div>
  );
}