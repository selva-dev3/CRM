import React from 'react';

export default function DealsPage() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">Deal Management (Kanban)</h1>
          <p className="text-gray-400 text-sm">Drag and drop deals across sales stages</p>
        </div>
        <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm">
          + New Deal
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 overflow-x-auto">
        {['Prospecting', 'Qualification', 'Proposal', 'Negotiation', 'Closed Won'].map((stage, idx) => (
          <div key={idx} className="bg-gray-900 border border-gray-800 rounded-xl p-4 min-w-[200px]">
            <h3 className="font-semibold text-sm text-gray-300 border-b border-gray-800 pb-2 mb-3">
              {stage}
            </h3>
            <div className="space-y-3">
              <div className="p-3 bg-gray-800 rounded-lg text-sm border border-gray-700">
                <p className="font-medium text-white">Acme Corp License</p>
                <p className="text-xs text-indigo-400 mt-1">$45,000</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
