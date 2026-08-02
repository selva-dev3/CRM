import React from 'react';

export default function NotificationsPage() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">Notifications</h1>
          <p className="text-gray-400 text-sm">Real-time alerts for lead updates, deals, and team mentions</p>
        </div>
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-gray-300">
        <p className="text-sm">Notification center ready.</p>
      </div>
    </div>
  );
}
