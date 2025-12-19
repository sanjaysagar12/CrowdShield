"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

interface Session {
  session_id: string;
  status: string;
  description: string;
  notify_to: string;
  created_at?: string;
  video_url?: string;
  live_url?: string;
  camera_id?: string;
  latitude?: string;
  longitude?: string;
}

interface ActiveCamerasResponse {
  cameras: string[];
}

export default function Dashboard() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeCameras, setActiveCameras] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      // Fetch active cameras
      const camRes = await fetch("http://localhost:8000/active_cameras");
      if (camRes.ok) {
        const camData: ActiveCamerasResponse = await camRes.json();
        setActiveCameras(camData.cameras);
      }

      // Fetch recent sessions
      const sessionRes = await fetch("http://localhost:8002/sessions");
      if (sessionRes.ok) {
        const sessionData: Session[] = await sessionRes.json();
        setSessions(sessionData.reverse()); // Show newest first
      }
    } catch (error) {
      console.error("Error fetching dashboard data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-7xl mx-auto space-y-8">

        {/* Header */}
        <header className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-gray-900">Security Command Center</h1>
            <p className="text-gray-500 mt-2">Real-time surveillance and incident monitoring</p>
          </div>
          <div className="flex gap-4">
            <div className="bg-white px-4 py-2 rounded-lg shadow-sm">
              <span className="block text-xs text-gray-400">Active Cameras</span>
              <span className="text-xl font-bold text-green-600">{activeCameras.length}</span>
            </div>
            <div className="bg-white px-4 py-2 rounded-lg shadow-sm">
              <span className="block text-xs text-gray-400">Recent Alerts</span>
              <span className="text-xl font-bold text-red-600">{sessions.length}</span>
            </div>
          </div>
        </header>

        {/* Live Active Streams Grid */}
        <section>
          <h2 className="text-2xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <span className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></span>
            Live Active Feeds
          </h2>
          {activeCameras.length === 0 ? (
            <div className="bg-white p-12 rounded-xl shadow-sm text-center text-gray-400 border-2 border-dashed border-gray-200">
              No active cameras detected. Start a vision model to see live feeds.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {activeCameras.map((camId) => (
                <div key={camId} className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-lg transition-shadow">
                  <div className="bg-black aspect-video relative group">
                    <iframe
                      src={`http://localhost:8000/video_feed/${camId}`}
                      className="w-full h-full border-0 pointer-events-none"
                      title={`Live ${camId}`}
                    />
                    <div className="absolute top-2 left-2 bg-red-600 text-white text-xs px-2 py-1 rounded font-bold uppercase tracking-wider">
                      LIVE
                    </div>
                  </div>
                  <div className="p-4 flex justify-between items-center">
                    <div>
                      <h3 className="font-bold text-gray-800">{camId}</h3>
                      <p className="text-xs text-green-600">Connection Stable</p>
                    </div>
                    {/* Placeholder for future controls */}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Recent Alerts List */}
        <section>
          <h2 className="text-2xl font-semibold text-gray-800 mb-4">Recent Alerts</h2>
          <div className="bg-white rounded-xl shadow-md overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Camera</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Location</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {sessions.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-8 text-center text-gray-500">No recent alerts found</td>
                    </tr>
                  ) : (
                    sessions.map((session) => (
                      <tr key={session.session_id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${session.status === 'approved' ? 'bg-green-100 text-green-800' :
                              session.status === 'rejected' ? 'bg-red-100 text-red-800' :
                                'bg-yellow-100 text-yellow-800'
                            }`}>
                            {session.status.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {session.camera_id || 'Unknown'}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                          {session.description}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {session.latitude && session.longitude ? `${session.latitude}, ${session.longitude}` : 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                          <Link href={`/session/${session.session_id}`} className="text-indigo-600 hover:text-indigo-900 bg-indigo-50 px-3 py-1 rounded-md transition-colors hover:bg-indigo-100">
                            View Details
                          </Link>
                        </td>
                      </tr>
                    )))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

      </div>
    </div>
  );
}
