'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { navigationConfig } from '@/config/navigation';
import { AIChatAssistant } from '@/components/ai/ai-chat-assistant';
import { getSessionToken, clearSessionToken } from '@/lib/api-client';
import { LogOut, Loader2, Zap, ShieldCheck, Menu, X } from 'lucide-react';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const pageTitle = React.useMemo(() => {
    if (!pathname || pathname === '/') return 'Dashboard';
    const segments = pathname.split('/').filter(Boolean);
    if (segments.length === 0) return 'Dashboard';

    const formattedSegments = segments.map((seg) => {
      // If segment is a UUID / ID format, replace with Details
      if (seg.length >= 20 || (seg.includes('-') && seg.length > 15) || /^[0-9a-fA-F-]+$/.test(seg)) {
        return 'Details';
      }
      return seg.charAt(0).toUpperCase() + seg.slice(1);
    });

    return formattedSegments.join(' / ');
  }, [pathname]);

  useEffect(() => {
    const token = getSessionToken();
    if (!token) {
      setIsAuthenticated(false);
      router.push('/login');
    } else {
      setIsAuthenticated(true);
    }
  }, [router, pathname]);

  // Close mobile menu on page change
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  const handleLogout = () => {
    clearSessionToken();
    router.push('/login');
  };

  // Show neutral loading spinner while verifying session token
  if (isAuthenticated === null) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-slate-50 text-slate-900 space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
        <p className="text-sm text-slate-900 font-bold">Verifying Session Token...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex h-screen bg-[#F9FAFB] text-[#111827] overflow-hidden font-sans relative">
      {/* Mobile Backdrop Overlay */}
      {isMobileMenuOpen && (
        <div
          onClick={() => setIsMobileMenuOpen(false)}
          className="fixed inset-0 z-40 bg-[#111827]/40 backdrop-blur-xs lg:hidden transition-opacity"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 w-64 border-r border-[#E5E7EB] bg-white flex flex-col shadow-saas-sm transform transition-transform duration-200 ease-in-out ${
          isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Brand Header */}
        <div className="p-5 border-b border-[#E5E7EB] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-btn bg-[#2563EB] flex items-center justify-center font-bold text-white shadow-saas-sm">
              <Zap className="w-5 h-5 fill-white/20 text-white" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-base text-[#111827] tracking-tight leading-none">
                Enterprise CRM
              </span>
              <span className="text-[10px] text-[#2563EB] font-semibold tracking-wider uppercase mt-1">
                Salesforce & HubSpot Style
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsMobileMenuOpen(false)}
            className="lg:hidden p-1.5 rounded-btn text-[#111827] hover:bg-[#F3F4F6] transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Nav Items */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          {navigationConfig.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3.5 py-2 rounded-btn text-button font-medium transition duration-150 ${
                  isActive
                    ? 'bg-[#2563EB]/10 text-[#2563EB] font-semibold border-l-4 border-[#2563EB]'
                    : 'text-[#374151] hover:text-[#2563EB] hover:bg-[#F3F4F6]'
                }`}
              >
                <span>{item.title}</span>
              </Link>
            );
          })}
        </nav>

        {/* Footer Org Badge */}
        <div className="p-4 border-t border-[#E5E7EB] bg-[#F9FAFB]">
          <div className="flex items-center space-x-2 text-caption text-[#374151] font-medium">
            <ShieldCheck className="w-4 h-4 text-[#16A34A] shrink-0" />
            <span className="truncate">Acme Enterprise Corp</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Header */}
        <header className="h-16 border-b border-[#E5E7EB] bg-white/90 backdrop-blur px-4 sm:px-6 flex items-center justify-between shadow-saas-sm">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              className="p-2 rounded-btn text-[#111827] hover:bg-[#F3F4F6] lg:hidden transition cursor-pointer"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h2 className="text-subheading font-semibold text-[#111827] tracking-tight truncate">
              {pageTitle}
            </h2>
          </div>

          <div className="flex items-center gap-2 sm:gap-4">
            <div className="hidden sm:inline-flex items-center space-x-2 px-2.5 py-1 rounded-full bg-slate-100 text-xs font-bold text-slate-900 border border-slate-200">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Multi-Tenant Org</span>
            </div>
            <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-900 border border-slate-200">
              Admin
            </div>
            <button
              type="button"
              onClick={handleLogout}
              title="Sign Out"
              className="p-2 rounded-xl text-slate-700 hover:text-rose-600 hover:bg-rose-50 transition cursor-pointer flex items-center gap-1.5 text-xs font-bold border border-transparent hover:border-rose-200"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </header>

        {/* Dynamic Page View */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 bg-slate-50">
          {children}
        </main>
      </div>

      {/* Global AI Assistant Floating Widget */}
      <AIChatAssistant />
    </div>
  );
}
