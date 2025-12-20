"use client";

import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from "next/link";
import {
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  FireIcon,
  UsersIcon,
  MapPinIcon,
  BellAlertIcon,
  VideoCameraIcon,
  InformationCircleIcon,
  EllipsisVerticalIcon,
  PlayIcon,
  PauseIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon
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

export default function SessionPage() {
  const params = useParams();
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Video player state
  const videoRef = useRef<HTMLVideoElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [isMuted, setIsMuted] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [progress, setProgress] = useState(0);

  // Format time as MM:SS
  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  // Handle video time update
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const current = videoRef.current.currentTime;
      const dur = videoRef.current.duration;
      setCurrentTime(current);
      setDuration(dur);
      setProgress((current / dur) * 100);
    }
  };

  // Handle seeking via progress bar click
  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (progressRef.current && videoRef.current) {
      const rect = progressRef.current.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const percentage = clickX / rect.width;
      const newTime = percentage * videoRef.current.duration;
      videoRef.current.currentTime = newTime;
      setCurrentTime(newTime);
      setProgress(percentage * 100);
    }
  };

  // Toggle play/pause
  const togglePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  // Toggle mute
  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  // Helper to get Icon based on description/type
  const getIconForSession = (desc: string) => {
    if (desc.toLowerCase().includes("fire")) return <FireIcon className="w-6 h-6 text-orange-500" />;
    if (desc.toLowerCase().includes("violence") || desc.toLowerCase().includes("weapon")) return <HandRaisedIcon className="w-6 h-6 text-red-600" />;
    if (desc.toLowerCase().includes("crowd")) return <UsersIcon className="w-6 h-6 text-amber-500" />;
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

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch all sessions for the top bar
        const allRes = await fetch("http://localhost:8002/sessions");
        if (allRes.ok) {
          let allData: Session[] = await allRes.json();
          allData = allData.reverse(); // Newest first
          setSessions(allData);

          // Find current session from list or fetch individual if needed (fetching list usually enough)
          const found = allData.find(s => s.session_id === params.id);
          if (found) {
            setCurrentSession(found);
          } else {
            // Fallback fetch if not in list (unlikely if list is complete)
            const singleRes = await fetch(`http://localhost:8002/session/${params.id}`);
            if (singleRes.ok) {
              setCurrentSession(await singleRes.json());
            } else {
              setError("Session not found");
            }
          }
        } else {
          throw new Error("Failed to fetch sessions");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    if (params.id) {
      fetchData();
    }
  }, [params.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl">Loading session...</div>
      </div>
    );
  }

  if (error || !currentSession) {
    return (
      <div className="flex items-center justify-center min-h-screen text-red-500">
        <div className="text-xl">Error: {error || "Session not found"}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 font-sans text-gray-900">

      {/* Top Navigation / Status Bar */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex justify-between items-center shadow-sm">
        <div className="flex items-center gap-3">
          <Link href="/">
            <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center text-white cursor-pointer">
              <ShieldCheckIcon className="w-5 h-5" />
            </div>
          </Link>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-gray-900">Crowd Shield</h1>
            <p className="text-[10px] text-gray-500 font-medium tracking-wide">SAFETY MONITOR</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="px-3 py-1 bg-green-50 text-green-700 border border-green-200 rounded-full text-[10px] font-bold flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span>
            SYSTEM ONLINE
          </div>

          <div className="flex gap-1.5">
            {['All', 'Fire', 'Violence', 'Stampede'].map(filter => (
              <button key={filter} className="px-2.5 py-1 rounded-full border border-gray-200 text-[10px] font-medium text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-colors">
                {filter}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 text-red-600 bg-red-50 px-2.5 py-1 rounded-md border border-red-100">
            <BellAlertIcon className="w-3.5 h-3.5" />
            <span className="text-[10px] font-bold">CRITICAL ALERTS ({sessions.filter(s => s.severity === 'Critical').length})</span>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-6 py-4 space-y-4">

        {/* Horizontal Alert Cards Scroll */}
        <section className="overflow-x-auto pb-2 custom-scrollbar">
          <div className="flex gap-4">
            {sessions.map(session => (
              <div
                key={session.session_id}
                onClick={() => router.push(`/session/${session.session_id}`)}
                className={`w-[320px] bg-white rounded-xl border-2 p-3 cursor-pointer transition-all hover:shadow-md flex flex-col shrink-0 ${currentSession?.session_id === session.session_id ? 'border-blue-500 ring-2 ring-blue-500/20' : 'border-gray-100 shadow-sm'
                  }`}
              >
                <div className="flex gap-3">
                  {/* Thumbnail */}
                  <div className="w-16 h-16 rounded-lg overflow-hidden bg-gray-200 shrink-0">
                    {session.video_url ? (
                      <video
                        src={session.video_url}
                        className="w-full h-full object-cover"
                        muted
                      />
                    ) : (
                      <div className="w-full h-full bg-gradient-to-br from-gray-700 to-gray-900 flex items-center justify-center">
                        {getIconForSession(session.description)}
                      </div>
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start gap-2">
                      <h3 className="font-bold text-gray-900 text-sm leading-tight truncate">
                        {session.description.split(':')[0] || "Alert"}
                      </h3>
                      <span className={`${getSeverityColor(session.severity)} text-white text-[9px] uppercase font-bold px-1.5 py-0.5 rounded shrink-0`}>
                        {session.severity || "NORMAL"}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-500 mt-0.5 flex items-center gap-1">
                      <MapPinIcon className="w-3 h-3 shrink-0" />
                      <span className="truncate">{session.camera_id} - Zone A</span>
                    </p>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-[10px] text-gray-400 font-mono">
                        {session.created_at ? session.created_at.split(' ')[1] : '00:00:00'} UTC
                      </span>
                      <span className="text-[10px] text-gray-600 font-semibold">
                        {session.confidence || "0%"} Match
                      </span>
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-2 mt-3 pt-2 border-t border-gray-100">
                  <button className="flex-1 text-[10px] font-bold text-green-600 bg-green-50 px-2 py-1.5 rounded hover:bg-green-100 transition-colors flex items-center justify-center gap-1">
                    <span>✓</span> APPROVE
                  </button>
                  <button className="flex-1 text-[10px] font-bold text-red-600 bg-red-50 px-2 py-1.5 rounded hover:bg-red-100 transition-colors flex items-center justify-center gap-1">
                    <span>✕</span> REJECT
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Main Interface Grid */}
        <section className="grid grid-cols-12 gap-6">
          {/* Live Feed */}
          <div className="col-span-12 h-[500px] relative group bg-black rounded-2xl overflow-hidden shadow-2xl border border-gray-800">
            {currentSession ? (
              <>
                <iframe
                  src={currentSession.live_url}
                  className="w-full h-full object-cover border-0"
                  allowFullScreen
                />

                {/* Overlay Controls */}
                <div className="absolute top-4 left-4 flex items-center gap-3">
                  <div className="flex items-center gap-2 bg-red-600/90 backdrop-blur-sm text-white px-3 py-1 rounded text-xs font-bold tracking-wider animate-pulse">
                    <span className="w-2 h-2 bg-white rounded-full"></span>
                    LIVE FEED
                  </div>
                  <div className="bg-black/60 backdrop-blur-sm text-gray-200 px-3 py-1 rounded text-xs font-mono border border-white/10 uppercase">
                    {currentSession.camera_id} - MAIN PLAZA
                  </div>
                </div>

                <div className="absolute top-4 right-4 flex gap-2">
                  <div className="bg-black/60 backdrop-blur-md px-2 py-1 rounded text-[10px] font-bold text-white border border-white/20 flex items-center gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-500"></div> AI: ON
                  </div>
                  <div className="bg-black/60 backdrop-blur-md px-2 py-1 rounded text-[10px] font-bold text-white border border-white/20">
                    4K • 60FPS
                  </div>
                </div>

                {/* Middle Action Overlay (Simulated) */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 border-2 border-red-500/50 bg-red-500/10 w-80 h-52 rounded-lg flex flex-col justify-between p-3 backdrop-blur-[2px]">
                  <div className="bg-red-600 text-white text-[10px] font-bold px-2 py-1 self-start rounded uppercase flex gap-1 items-center">
                    <ExclamationTriangleIcon className="w-3 h-3" />
                    {currentSession.description.split(':')[0]}
                  </div>
                  <div className="bg-black/80 backdrop-blur text-white p-3 rounded border border-white/10">
                    <div className="flex justify-between items-end mb-1">
                      <span className="text-[10px] font-bold uppercase text-gray-400">Confidence</span>
                      <span className="text-red-500 font-mono font-bold text-sm">{currentSession.confidence || "0%"}</span>
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
          <div className="col-span-8 bg-black rounded-xl overflow-hidden relative border border-gray-800 h-[280px] shadow-lg">
            <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
              <VideoCameraIcon className="w-4 h-4 text-orange-500" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">Looping Clip</span>
            </div>
            <div className="absolute top-4 left-32 z-10">
              <span className="text-[10px] text-gray-400 font-mono">INCIDENT #{currentSession?.session_id.slice(0, 8)} • {currentSession?.description.toUpperCase()}</span>
            </div>
            {currentSession && currentSession.video_url ? (
              <video
                ref={videoRef}
                src={currentSession.video_url}
                className="w-full h-full object-contain"
                autoPlay
                loop
                muted={isMuted}
                playsInline
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={handleTimeUpdate}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-600 text-xs font-mono uppercase bg-gray-900">
                No Recorded Clip Available
              </div>
            )}
            {/* Player Controls */}
            <div className="absolute bottom-0 w-full bg-gradient-to-t from-black/90 to-transparent p-4">
              {/* Seekable Progress Bar */}
              <div
                ref={progressRef}
                className="w-full h-2 bg-gray-700 rounded-full mb-3 cursor-pointer group"
                onClick={handleSeek}
              >
                <div
                  className="h-full bg-blue-500 rounded-full relative transition-all"
                  style={{ width: `${progress}%` }}
                >
                  {/* Seek Handle */}
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-lg opacity-0 group-hover:opacity-100 transition-opacity"></div>
                </div>
              </div>
              <div className="flex justify-between items-center text-gray-400">
                <div className="flex items-center gap-3">
                  {/* Play/Pause Button */}
                  <button
                    onClick={togglePlayPause}
                    className="w-8 h-8 flex items-center justify-center bg-white/10 hover:bg-white/20 rounded-full transition-colors"
                  >
                    {isPlaying ? (
                      <PauseIcon className="w-4 h-4 text-white" />
                    ) : (
                      <PlayIcon className="w-4 h-4 text-white" />
                    )}
                  </button>
                  {/* Mute Button */}
                  <button
                    onClick={toggleMute}
                    className="w-8 h-8 flex items-center justify-center bg-white/10 hover:bg-white/20 rounded-full transition-colors"
                  >
                    {isMuted ? (
                      <SpeakerXMarkIcon className="w-4 h-4 text-white" />
                    ) : (
                      <SpeakerWaveIcon className="w-4 h-4 text-white" />
                    )}
                  </button>
                  {/* Time Display */}
                  <span className="text-white text-xs font-mono">
                    {formatTime(currentTime)} / {formatTime(duration || 0)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="col-span-4 bg-white rounded-xl shadow-lg border border-gray-100 p-5 h-[280px] flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-gray-900 flex items-center gap-2 text-sm">
                <InformationCircleIcon className="w-5 h-5 text-gray-400" />
                Clip Details
              </h3>
              <button className="text-gray-400 hover:text-gray-600">
                <EllipsisVerticalIcon className="w-5 h-5" />
              </button>
            </div>

            <div className="flex items-start gap-3 mb-4">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center border shrink-0 ${currentSession?.description.toLowerCase().includes('fire') ? 'bg-red-50 border-red-100' :
                currentSession?.description.toLowerCase().includes('crowd') ? 'bg-orange-50 border-orange-100' :
                  'bg-gray-50 border-gray-100'
                }`}>
                {currentSession ? getIconForSession(currentSession.description) : null}
              </div>
              <div className="min-w-0">
                <h4 className="font-bold text-gray-900 text-sm leading-tight">
                  {currentSession?.description || "No Incident Selected"}
                </h4>
                <p className="text-xs text-gray-500 leading-relaxed mt-1">
                  AI detected patterns consistent with {currentSession?.severity || "Normal"} activity.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 mt-auto">
              <div className="bg-gray-50 p-2.5 rounded-lg border border-gray-100 hover:border-gray-200 transition-colors">
                <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">Time</div>
                <div className="font-mono font-bold text-gray-700 text-sm">{currentSession?.created_at?.split(' ')[1] || "00:00:00"} UTC</div>
              </div>
              <div className="bg-gray-50 p-2.5 rounded-lg border border-gray-100 hover:border-gray-200 transition-colors">
                <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">Confidence</div>
                <div className="font-mono font-bold text-green-600 text-sm">{currentSession?.confidence || "--%"}</div>
              </div>
              <div className="bg-gray-50 p-2.5 rounded-lg border border-gray-100 hover:border-gray-200 transition-colors">
                <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">Camera</div>
                <div className="font-mono font-bold text-gray-700 text-sm">{currentSession?.camera_id} (Static)</div>
              </div>
              <div className="bg-gray-50 p-2.5 rounded-lg border border-gray-100 hover:border-gray-200 transition-colors">
                <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">Zone</div>
                <div className="font-mono font-bold text-gray-700 text-sm">Corridor A</div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
