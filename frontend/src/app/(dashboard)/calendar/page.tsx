import React from 'react';

export default function CalendarPage() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">Calendar</h1>
          <p className="text-gray-400 text-sm">Synchronized Google Calendar & Outlook schedule</p>
        </div>
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-gray-300">
        <p className="text-sm">Interactive calendar grid ready.</p>
      </div>
    </div>
  );
}
