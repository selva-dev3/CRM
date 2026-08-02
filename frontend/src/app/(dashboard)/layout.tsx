'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { navigationConfig } from '@/config/navigation';
import { AIChatAssistant } from '@/components/ai/ai-chat-assistant';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 border-r border-gray-800 bg-gray-900 flex flex-col">
        <div className="p-5 border-b border-gray-800 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white">
            CRM
          </div>
          <span className="font-bold text-lg text-white tracking-wide">Enterprise CRM</span>
        </div>
        <nav className="flex-1 overflow-y-auto p-4 space-y-1">
          {navigationConfig.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition ${
                  isActive
                    ? 'bg-indigo-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`}
              >
                <span>{item.title}</span>
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 border-b border-gray-800 bg-gray-900/50 backdrop-blur px-6 flex items-center justify-between">
          <h2 className="text-xl font-semibold capitalize">
            {pathname.replace('/', '') || 'Dashboard'}
          </h2>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-400">Multi-Tenant Org</span>
            <div className="w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center text-sm font-medium border border-gray-700">
              Admin
            </div>
          </div>
        </header>

        {/* Dynamic Page View */}
        <main className="flex-1 overflow-y-auto p-6 bg-gray-950">
          {children}
        </main>
      </div>

      {/* Global AI Assistant Floating Widget */}
      <AIChatAssistant />
    </div>
  );
}
