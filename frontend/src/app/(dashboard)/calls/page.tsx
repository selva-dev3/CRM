import React from 'react';

export default function CallsPage() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">Call Logs & Twilio</h1>
          <p className="text-gray-400 text-sm">Log call notes and initiate click-to-call via Twilio</p>
        </div>
        <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm">
          + Log Call
        </button>
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-gray-300">
        <p className="text-sm">Call activity log ready.</p>
      </div>
    </div>
  );
}
