'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { navigationConfig } from '@/config/navigation';
import { AIChatAssistant } from '@/components/ai/ai-chat-assistant';
import { getSessionToken, clearSessionToken } from '@/lib/api-client';
import { LogOut, Loader2 } from 'lucide-react';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const token = getSessionToken();
    if (!token) {
      setIsAuthenticated(false);
      router.push('/login');
    } else {
      setIsAuthenticated(true);
    }
  }, [router, pathname]);

  const handleLogout = () => {
    clearSessionToken();
    router.push('/login');
  };

  // Show loading spinner while verifying session token
  if (isAuthenticated === null) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-gray-950 text-white space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
        <p className="text-sm text-gray-400 font-medium">Verifying Session Token...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 border-r border-gray-800 bg-gray-900 flex flex-col">
        <div className="p-5 border-b border-gray-800 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-600/30">
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
            <button
              type="button"
              onClick={handleLogout}
              title="Sign Out"
              className="p-2 rounded-lg text-gray-400 hover:text-rose-400 hover:bg-gray-800 transition cursor-pointer flex items-center gap-1.5 text-xs font-medium"
            >
              <LogOut className="w-4 h-4" />
              <span>Logout</span>
            </button>
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
