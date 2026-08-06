'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { navigationSections, NavSection, NavItem } from '@/config/navigation';
import { AIChatAssistant } from '@/components/ai/ai-chat-assistant';
import { getSessionToken, clearSessionToken } from '@/lib/api-client';
import { useCurrentOrganizationQuery } from '@/lib/api/organizations';
import {
  LogOut,
  Loader2,
  Zap,
  ShieldCheck,
  Menu,
  X,
  LayoutDashboard,
  UserPlus,
  Users,
  Building2,
  Kanban,
  CheckSquare,
  CalendarDays,
  PhoneCall,
  Mail,
  StickyNote,
  FileText,
  Package,
  FileSpreadsheet,
  Receipt,
  BarChart3,
  Calendar,
  Bell,
  UserCog,
  Settings,
  Building,
  Layers,
  ChevronDown,
  ChevronRight
} from 'lucide-react';

const ICON_MAP: Record<string, React.ElementType> = {
  LayoutDashboard,
  UserPlus,
  Users,
  Building2,
  Kanban,
  CheckSquare,
  CalendarDays,
  PhoneCall,
  Mail,
  StickyNote,
  FileText,
  Package,
  FileSpreadsheet,
  Receipt,
  BarChart3,
  Calendar,
  Bell,
  UserCog,
  ShieldCheck,
  Settings,
  Building,
  Layers
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: currentOrg } = useCurrentOrganizationQuery();
  const [orgDisplayName, setOrgDisplayName] = useState<string>('');
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    CRM: true,
    Analytics: true,
    Administration: true
  });

  useEffect(() => {
    if (currentOrg?.name) {
      setOrgDisplayName(currentOrg.name);
    } else if (typeof window !== 'undefined') {
      try {
        const storedUser = localStorage.getItem('user');
        if (storedUser) {
          const parsed = JSON.parse(storedUser);
          const name = parsed?.organization?.name || parsed?.organization_name || parsed?.org_name;
          if (name) setOrgDisplayName(name);
        }
      } catch {
        // fallback
      }
    }
  }, [currentOrg]);

  const pageTitle = React.useMemo(() => {
    if (!pathname || pathname === '/') return 'Dashboard';
    const segments = pathname.split('/').filter(Boolean);
    if (segments.length === 0) return 'Dashboard';

    const formattedSegments = segments.map((seg) => {
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

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  const toggleSection = (title: string) => {
    setOpenSections((prev) => ({
      ...prev,
      [title]: !prev[title]
    }));
  };

  const handleLogout = () => {
    clearSessionToken();
    if (typeof window !== 'undefined') {
      localStorage.removeItem('user');
      sessionStorage.removeItem('user');
    }
    router.push('/login');
  };

  if (isAuthenticated === null) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-slate-50 text-slate-900 space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
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

      {/* Fixed Sidebar (Width w-64 / 256px) */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 border-r border-[#E5E7EB] bg-white flex flex-col shadow-sm transform transition-transform duration-200 ease-in-out ${
          isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Brand Header */}
        <div className="p-4 border-b border-[#E5E7EB] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#2563EB] flex items-center justify-center font-bold text-white shadow-xs shrink-0">
              <Zap className="w-5 h-5 fill-white/20 text-white" />
            </div>
            <div className="flex flex-col min-w-0">
              <span className="font-bold text-base text-[#111827] tracking-tight leading-none truncate">
                Enterprise CRM
              </span>
              <span className="text-[10px] text-[#2563EB] font-bold tracking-wider uppercase mt-1 truncate">
                Salesforce Style
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsMobileMenuOpen(false)}
            className="lg:hidden p-1.5 rounded text-[#111827] hover:bg-[#F3F4F6] transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Structured Nav Sections */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin">
          {navigationSections.map((section: NavSection, idx: number) => {
            const hasTitle = Boolean(section.title);
            const sectionKey = section.title || `section-${idx}`;
            const isOpen = openSections[sectionKey] !== false;

            return (
              <div key={sectionKey} className="space-y-1">
                {hasTitle && (
                  <button
                    type="button"
                    onClick={() => toggleSection(sectionKey)}
                    className="w-full flex items-center justify-between px-2 py-1.5 text-[11px] font-bold tracking-wider text-slate-500 uppercase hover:text-slate-900 cursor-pointer transition select-none group"
                  >
                    <span className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-500/60 group-hover:bg-blue-600 transition" />
                      {section.title}
                    </span>
                    {isOpen ? (
                      <ChevronDown className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-600" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-600" />
                    )}
                  </button>
                )}

                {isOpen && (
                  <div className={hasTitle ? 'pl-2 space-y-0.5 border-l-2 border-slate-100 ml-2.5' : 'space-y-0.5'}>
                    {section.items.map((item: NavItem) => {
                      const isActive = pathname === item.href || (item.href === '/email' && pathname === '/emails');
                      const IconComponent = ICON_MAP[item.icon] || LayoutDashboard;

                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          className={`flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition duration-150 relative ${
                            isActive
                              ? 'bg-blue-50 text-blue-600 font-bold border-l-4 border-blue-600'
                              : 'text-slate-600 hover:text-blue-600 hover:bg-slate-50'
                          }`}
                        >
                          <IconComponent
                            className={`w-4 h-4 shrink-0 ${isActive ? 'text-blue-600' : 'text-slate-400'}`}
                          />
                          <span className="truncate">{item.title}</span>
                          {item.badge && (
                            <span className="ml-auto px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-blue-100 text-blue-700">
                              {item.badge}
                            </span>
                          )}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* Footer Org Badge (Links to Settings Page) */}
        <Link
          href="/settings"
          title="Organization Settings"
          className="p-3.5 border-t border-[#E5E7EB] bg-[#F9FAFB] hover:bg-slate-100 text-[#374151] shrink-0 transition flex items-center justify-between group"
        >
          <div className="flex items-center space-x-2 text-xs font-bold min-w-0">
            <ShieldCheck className="w-4 h-4 text-[#16A34A] shrink-0" />
            <span className="truncate group-hover:text-blue-600 transition">{orgDisplayName || currentOrg?.name || 'Organization'}</span>
          </div>
          <Settings className="w-4 h-4 text-slate-400 group-hover:text-blue-600 transition shrink-0" />
        </Link>
      </aside>

      {/* Main Content Area (padded left for fixed sidebar w-64) */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0 lg:pl-64">
        {/* Header */}
        <header className="h-16 border-b border-[#E5E7EB] bg-white/95 backdrop-blur px-4 sm:px-6 flex items-center justify-between shadow-xs shrink-0">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              className="p-1.5 rounded-lg text-[#111827] hover:bg-[#F3F4F6] lg:hidden transition cursor-pointer"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h2 className="text-base font-bold text-[#111827] tracking-tight truncate">
              {pageTitle}
            </h2>
          </div>

          <div className="flex items-center gap-2 sm:gap-4">
            <div className="hidden sm:inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-100 text-xs font-bold text-slate-900 border border-slate-200">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Multi-Tenant Org</span>
            </div>

            <Link
              href="/notifications"
              title="Notifications"
              className={`p-2 rounded-xl transition cursor-pointer relative border flex items-center justify-center ${
                pathname === '/notifications'
                  ? 'bg-blue-50 text-blue-600 border-blue-300 shadow-xs'
                  : 'bg-slate-50 text-slate-700 hover:text-blue-600 hover:bg-slate-100 border-slate-200'
              }`}
            >
              <Bell className="w-4.5 h-4.5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-blue-600 ring-2 ring-white" />
            </Link>

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
