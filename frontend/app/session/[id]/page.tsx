"use client";

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';

interface Session {
  session_id: string;
  notify_to: string;
  status: string;
  description: string;
  live_url: string;
  video_url: string;
  camera_id: string;
  latitude: string;
  longitude: string;
}

export default function SessionPage() {
  const params = useParams();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSession = async () => {
      try {
        const response = await fetch(`http://localhost:8002/session/${params.id}`);
        if (!response.ok) {
          throw new Error('Failed to fetch session data');
        }
        const data = await response.json();
        setSession(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    if (params.id) {
      fetchSession();
    }
  }, [params.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl">Loading session...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen text-red-500">
        <div className="text-xl">Error: {error}</div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl">Session not found</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header Section */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h1 className="text-3xl font-bold text-gray-800 mb-4">Crowd Shield Session</h1>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">Session ID</p>
              <p className="font-mono text-sm">{session.session_id}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Status</p>
              <span className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${session.status === 'approved' ? 'bg-green-100 text-green-800' :
                  session.status === 'rejected' ? 'bg-red-100 text-red-800' :
                    'bg-yellow-100 text-yellow-800'
                }`}>
                {session.status.toUpperCase()}
              </span>
            </div>
            <div>
              <p className="text-sm text-gray-500">Camera Source</p>
              <p className="font-mono text-sm text-blue-600">{session.camera_id}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Location</p>
              <p className="font-mono text-sm" title={`${session.latitude}, ${session.longitude}`}>
                {session.latitude}, {session.longitude}
                <a
                  href={`https://www.google.com/maps/search/?api=1&query=${session.latitude},${session.longitude}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-2 text-xs text-blue-500 hover:underline"
                >
                  (View Map)
                </a>
              </p>
            </div>
            <div className="md:col-span-2">
              <p className="text-sm text-gray-500">Description</p>
              <p className="text-gray-800">{session.description}</p>
            </div>
            <div className="md:col-span-2">
              <p className="text-sm text-gray-500">Notified Recipients</p>
              <p className="text-gray-800">{session.notify_to}</p>
            </div>
          </div>
        </div>

        {/* Live Stream Section */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-bold text-gray-800 mb-4">Live Surveillance Feed ({session.camera_id})</h2>
          <div className="aspect-video w-full bg-black rounded-lg overflow-hidden relative">
            <iframe
              src={session.live_url}
              className="w-full h-full border-0"
              allow="camera; microphone"
              title="Live Stream"
            />
          </div>
          <div className="mt-4 text-sm text-gray-500">
            <p>Live feed source: {session.live_url}</p>
          </div>
        </div>

        {/* Recorded Video Section */}
        {session.video_url && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-bold text-gray-800 mb-4">Recorded Incident Video</h2>
            <div className="aspect-video w-full bg-black rounded-lg overflow-hidden relative">
              <video
                src={session.video_url}
                controls
                className="w-full h-full"
              >
                Your browser does not support the video tag.
              </video>
            </div>
            <div className="mt-4 text-sm text-gray-500">
              <p>Video source: {session.video_url}</p>
              <a href={session.video_url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">
                Download / Open directly
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
