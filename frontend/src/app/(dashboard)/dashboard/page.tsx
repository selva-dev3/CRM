import React from 'react';

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">Sales & CRM Analytics</h1>
          <p className="text-gray-400 text-sm">Real-time performance metrics and AI forecast insights</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { title: 'Total Leads', value: '1,248', change: '+12%' },
          { title: 'Deals Won', value: '$452,000', change: '+18%' },
          { title: 'Win Rate', value: '64.2%', change: '+3.4%' },
          { title: 'AI Lead Quality Score', value: '88/100', change: 'Optimal' },
        ].map((stat, i) => (
          <div key={i} className="p-5 bg-gray-900 border border-gray-800 rounded-xl">
            <p className="text-sm text-gray-400">{stat.title}</p>
            <p className="text-2xl font-bold text-white mt-1">{stat.value}</p>
            <span className="text-xs text-emerald-400">{stat.change}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
