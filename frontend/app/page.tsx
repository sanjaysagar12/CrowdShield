"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import {
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  FireIcon,
  UsersIcon,  // Note: Heroicons might not have this exact name, using generic if needed or SVGs
  MapPinIcon,
  ClockIcon,
  VideoCameraIcon,
  CheckCircleIcon,
  XCircleIcon,
  BellAlertIcon
} from '@heroicons/react/24/solid';

// Fallback for missing icon
const HandRaisedIcon = ExclamationTriangleIcon;

interface Session {
  session_id: string;
  status: string;
  description: string;
  notify_to: string;
  created_at: string;
  video_url: string;
  live_url: string;
  camera_id: string;
  latitude: string;
  longitude: string;
  severity: "Critical" | "Warning" | "Informational" | "Normal";
  confidence: string;
}

export default function Dashboard() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  // Poll for data
  const fetchData = async () => {
    try {
      const res = await fetch("http://localhost:8002/sessions");
      if (res.ok) {
        const data: Session[] = await res.json();
        // Sort by newest first
        const sorted = data.reverse();
        setSessions(sorted);

        // Auto-select the first session if none selected
        if (!selectedSession && sorted.length > 0) {
          setSelectedSession(sorted[0]);
        }
      }
    } catch (error) {
      console.error("Error fetching sessions:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000); // 3s polling
    return () => clearInterval(interval);
  }, []);

  // Helper to get Icon based on description/type
  const getIconForSession = (desc: string) => {
    if (desc.toLowerCase().includes("fire")) return <FireIcon className="w-6 h-6 text-orange-500" />;
    if (desc.toLowerCase().includes("violence") || desc.toLowerCase().includes("weapon")) return <HandRaisedIcon className="w-6 h-6 text-red-600" />;
    if (desc.toLowerCase().includes("crowd")) return <UsersIcon className="w-6 h-6 text-amber-500" />; // Assuming fallback
    return <ExclamationTriangleIcon className="w-6 h-6 text-gray-500" />;
  };

  // Helper for Severity Color
  const getSeverityColor = (sev: string) => {
    switch (sev?.toLowerCase()) {
      case 'critical': return 'bg-red-600';
      case 'warning': return 'bg-orange-500';
      case 'informational': return 'bg-blue-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 font-sans text-gray-900">

      {/* Top Navigation / Status Bar */}
      <header className="bg-white border-b border-gray-200 px-8 py-4 flex justify-between items-center shadow-sm">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center text-white">
            <ShieldCheckIcon className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-gray-900">Crowd Shield</h1>
            <p className="text-xs text-gray-500 font-medium tracking-wide">SAFETY MONITOR</p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="px-4 py-1.5 bg-green-50 text-green-700 border border-green-200 rounded-full text-xs font-bold flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
            SYSTEM ONLINE
          </div>

          <div className="flex gap-2">
            {['All', 'Fire', 'Violence', 'Stampede'].map(filter => (
              <button key={filter} className="px-3 py-1 rounded-full border border-gray-200 text-xs font-medium text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-colors">
                {filter}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 text-red-600 bg-red-50 px-3 py-1.5 rounded-md border border-red-100">
            <BellAlertIcon className="w-4 h-4" />
            <span className="text-xs font-bold">CRITICAL ALERTS ({sessions.filter(s => s.severity === 'Critical').length})</span>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto p-6 space-y-6">

        {/* Horizontal Alert Cards Scroll */}
        <section className="overflow-x-auto pb-4 custom-scrollbar">
          <div className="flex gap-4 min-w-max">
            {sessions.map(session => (
              <div
                key={session.session_id}
                onClick={() => setSelectedSession(session)}
                className={`w-96 bg-white rounded-xl border-2 p-4 cursor-pointer transition-all hover:shadow-md flex flex-col justify-between shrink-0 ${selectedSession?.session_id === session.session_id ? 'border-blue-500 ring-2 ring-blue-500/20' : 'border-white shadow-sm'
                  }`}
              >
                <div className="flex justify-between items-start mb-3">
                  <div className="flex gap-3">
                    <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center border border-gray-200">
                      {getIconForSession(session.description)}
                    </div>
                    <div>
                      <h3 className="font-bold text-gray-900 leading-tight">{session.description.split(':')[0] || "Alert"}</h3>
                      <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                        <MapPinIcon className="w-3 h-3" />
                        {session.camera_id} - Zone A
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5 font-mono">
                        {session.created_at.split(' ')[1]} UTC
                      </p>
                    </div>
                  </div>
                  <span className={`${getSeverityColor(session.severity)} text-white text-[10px] uppercase font-bold px-2 py-0.5 rounded`}>
                    {session.severity || "NORMAL"}
                  </span>
                </div>

                <div className="flex justify-between items-center bg-gray-50 rounded-lg p-2 mt-2">
                  <div className="text-xs font-medium text-gray-600">Match Confidence</div>
                  <div className="text-sm font-bold text-gray-900">{session.confidence || "N/A"}</div>
                </div>

                <div className="grid grid-cols-2 gap-2 mt-4">
                  <button className="flex items-center justify-center gap-1 bg-green-600 hover:bg-green-700 text-white py-1.5 rounded-md text-xs font-bold transition-colors">
                    <CheckCircleIcon className="w-4 h-4" /> APPROVE
                  </button>
                  <button className="flex items-center justify-center gap-1 bg-white border border-gray-200 hover:bg-red-50 hover:text-red-600 hover:border-red-200 text-gray-600 py-1.5 rounded-md text-xs font-bold transition-colors">
                    <XCircleIcon className="w-4 h-4" /> REJECT
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Main Interface Grid */}
        <section className="grid grid-cols-12 gap-6 h-[700px]">

          {/* Live Feed (Spans Full Width of Top Row if we wanted, but sticking to requested layout) 
                Wait, prompt said Middle Section is Live Feed. But usually dashboard has hierarchical view. 
                Let's make the Top 2/3rds the Live Feed and Bottom 1/3rd split between Clip and Details.
            */}

          <div className="col-span-12 h-[55%] relative group bg-black rounded-2xl overflow-hidden shadow-2xl border border-gray-800">
            {selectedSession ? (
              <>
                <iframe
                  src={selectedSession.live_url}
                  className="w-full h-full object-cover border-0"
                  allowFullScreen
                />

                {/* Overlay Controls */}
                <div className="absolute top-6 left-6 flex items-center gap-3">
                  <div className="flex items-center gap-2 bg-red-600/90 backdrop-blur-sm text-white px-3 py-1 rounded text-xs font-bold tracking-wider animate-pulse">
                    <span className="w-2 h-2 bg-white rounded-full"></span>
                    LIVE FEED
                  </div>
                  <div className="bg-black/60 backdrop-blur-sm text-gray-200 px-3 py-1 rounded text-xs font-mono border border-white/10 uppercase">
                    {selectedSession.camera_id} - MAIN PLAZA
                  </div>
                </div>

                <div className="absolute top-6 right-6 flex gap-2">
                  <div className="bg-black/60 backdrop-blur-md px-2 py-1 rounded text-[10px] font-bold text-white border border-white/20 flex items-center gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-500"></div> AI: ON
                  </div>
                  <div className="bg-black/60 backdrop-blur-md px-2 py-1 rounded text-[10px] font-bold text-white border border-white/20">
                    4K • 60FPS
                  </div>
                </div>

                {/* Middle Action Overlay (Simulated) */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 border-2 border-red-500/50 bg-red-500/10 w-96 h-64 rounded-lg flex flex-col justify-between p-4 backdrop-blur-[2px]">
                  <div className="bg-red-600 text-white text-xs font-bold px-2 py-1 self-start rounded uppercase flex gap-1 items-center">
                    <ExclamationTriangleIcon className="w-3 h-3" />
                    POTENTIAL {selectedSession.description.split(':')[0]}
                  </div>
                  <div className="bg-black/80 backdrop-blur text-white p-3 rounded border border-white/10">
                    <div className="flex justify-between items-end mb-1">
                      <span className="text-[10px] font-bold uppercase text-gray-400">Confidence</span>
                      <span className="text-red-500 font-mono font-bold">{selectedSession.confidence || "0%"}</span>
                    </div>
                    <div className="w-full h-1 bg-gray-800 rounded-full overflow-hidden">
                      <div className="h-full bg-red-600 w-[94%]"></div>
                    </div>
                    <div className="flex gap-2 mt-3">
                      <button className="flex-1 bg-gray-700 hover:bg-gray-600 text-[10px] py-1.5 rounded font-bold transition-colors">IGNORE</button>
                      <button className="flex-1 bg-red-600 hover:bg-red-700 text-[10px] py-1.5 rounded font-bold transition-colors">ALERT TEAM</button>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-500 font-mono">
                Select a session to view live feed
              </div>
            )}
          </div>

          {/* Bottom Row: Recorded Clip (Left) and Details (Right) */}
          <div className="col-span-8 bg-black rounded-xl overflow-hidden relative border border-gray-800 h-[42%] shadow-lg">
            <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
              <VideoCameraIcon className="w-4 h-4 text-orange-500" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">Looping Clip</span>
              <span className="text-[10px] text-gray-400 font-mono">INCIDENT #{selectedSession?.session_id.slice(0, 8)}</span>
            </div>
            {selectedSession && selectedSession.video_url ? (
              <video
                src={selectedSession.video_url}
                className="w-full h-full object-cover opacity-80"
                autoPlay loop muted playsInline
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-600 bg-gray-900 border-2 border-dashed border-gray-800">
                <p>No recorded clip available</p>
              </div>
            )}
          </div>

          <div className="col-span-4 bg-white rounded-xl shadow-lg border border-gray-100 p-6 h-[42%] flex flex-col">
            <div className="flex justify-between items-center mb-6">
              <h3 className="font-bold text-gray-800 flex items-center gap-2">
                <div className="bg-gray-200 p-1 rounded-full"><div className="w-1 h-1 bg-gray-500 rounded-full"></div></div>
                Clip Details
              </h3>
              <button className="text-gray-400 hover:text-gray-600"><span className="text-xl">⋮</span></button>
            </div>

            <div className="flex items-start gap-4 mb-8">
              <div className="w-12 h-12 rounded-lg bg-red-50 flex items-center justify-center shrink-0">
                {selectedSession ? getIconForSession(selectedSession.description) : <div />}
              </div>
              <div>
                <h4 className="font-bold text-gray-900 text-lg">
                  {selectedSession?.description || "No Incident Selected"}
                </h4>
                <p className="text-sm text-gray-500 leading-relaxed mt-1">
                  AI detected patterns consistent with {selectedSession?.severity || "Normal"} activity.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mt-auto">
              <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Time</div>
                <div className="font-mono font-medium text-gray-800">{selectedSession?.created_at.split(' ')[1] || "--:--"} UTC</div>
              </div>
              <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Confidence</div>
                <div className="font-mono font-bold text-green-600">{selectedSession?.confidence || "--%"}</div>
              </div>
              <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Camera</div>
                <div className="font-mono font-medium text-gray-800">{selectedSession?.camera_id || "CAM 01"} (Static)</div>
              </div>
              <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Zone</div>
                <div className="font-mono font-medium text-gray-800">Corridor A</div>
              </div>
            </div>
          </div>

        </section>
      </main>
    </div>
  );
}
