'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  Search,
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
  ShieldCheck,
  Settings,
  ArrowRight
} from 'lucide-react';

interface SearchItem {
  id: string;
  title: string;
  category: string;
  href: string;
  description: string;
  icon: React.ElementType;
}

const SEARCH_ITEMS: SearchItem[] = [
  { id: 'dashboard', title: 'Dashboard', category: 'General', href: '/dashboard', description: 'Overview metrics & analytics', icon: LayoutDashboard },
  { id: 'leads', title: 'Leads', category: 'CRM', href: '/leads', description: 'Manage and score sales leads', icon: UserPlus },
  { id: 'contacts', title: 'Contacts', category: 'CRM', href: '/contacts', description: 'Customer & business contact directory', icon: Users },
  { id: 'companies', title: 'Companies', category: 'CRM', href: '/companies', description: 'Accounts and enterprise clients', icon: Building2 },
  { id: 'deals', title: 'Deals & Pipeline', category: 'CRM', href: '/deals', description: 'Kanban sales opportunities & pipeline', icon: Kanban },
  { id: 'tasks', title: 'Tasks', category: 'CRM', href: '/tasks', description: 'Activity management and follow-ups', icon: CheckSquare },
  { id: 'meetings', title: 'Meetings', category: 'CRM', href: '/meetings', description: 'Calendar schedules & Zoom integrations', icon: CalendarDays },
  { id: 'calls', title: 'Calls', category: 'CRM', href: '/calls', description: 'Call logs & telephony records', icon: PhoneCall },
  { id: 'emails', title: 'Emails', category: 'CRM', href: '/emails', description: 'Mail campaigns & inbox sync', icon: Mail },
  { id: 'notes', title: 'Notes', category: 'CRM', href: '/notes', description: 'Quick meeting notes & workspace logs', icon: StickyNote },
  { id: 'documents', title: 'Documents', category: 'CRM', href: '/documents', description: 'Contracts, proposals & files', icon: FileText },
  { id: 'products', title: 'Products', category: 'CRM', href: '/products', description: 'Product catalog & price lists', icon: Package },
  { id: 'quotes', title: 'Quotes', category: 'CRM', href: '/quotes', description: 'Price estimates & sales quotes', icon: FileSpreadsheet },
  { id: 'invoices', title: 'Invoices', category: 'CRM', href: '/invoices', description: 'Billing gateway & recurring invoices', icon: Receipt },
  { id: 'reports', title: 'Reports', category: 'Analytics', href: '/reports', description: 'Sales performance & forecasting analytics', icon: BarChart3 },
  { id: 'calendar', title: 'Calendar', category: 'Analytics', href: '/calendar', description: 'Schedule planner & team events', icon: Calendar },
  { id: 'notifications', title: 'Notifications', category: 'General', href: '/notifications', description: 'Real-time activity alerts', icon: Bell },
  { id: 'users', title: 'User Management', category: 'Administration', href: '/users', description: 'Manage system users & team members', icon: UserCog },
  { id: 'roles', title: 'Roles & Permissions', category: 'Administration', href: '/roles', description: 'RBAC matrix & security settings', icon: ShieldCheck },
  { id: 'settings', title: 'System Settings', category: 'Administration', href: '/settings', description: 'Organization preferences & webhooks', icon: Settings },
];

interface GlobalSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function GlobalSearchModal({ isOpen, onClose }: GlobalSearchModalProps) {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Filter items based on query
  const filteredItems = React.useMemo(() => {
    if (!query.trim()) return SEARCH_ITEMS;
    const q = query.toLowerCase().trim();
    return SEARCH_ITEMS.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        item.category.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q)
    );
  }, [query]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    }
  }, [isOpen]);

  // Reset selected index when query changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Keyboard navigation inside modal
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev < filteredItems.length - 1 ? prev + 1 : 0));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : filteredItems.length - 1));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filteredItems[selectedIndex]) {
          handleSelect(filteredItems[selectedIndex].href);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, filteredItems, selectedIndex]);

  const handleSelect = (href: string) => {
    onClose();
    router.push(href);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 px-4 bg-slate-900/60 backdrop-blur-xs transition-opacity animate-in fade-in duration-200">
      {/* Backdrop click to close */}
      <div className="fixed inset-0" onClick={onClose} />

      {/* Dialog box */}
      <div className="relative w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col z-10 animate-in zoom-in-95 duration-150">
        {/* Search Header Input */}
        <div className="flex items-center px-4 border-b border-slate-100 bg-slate-50/50">
          <Search className="w-5 h-5 text-slate-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search CRM pages, modules, settings..."
            className="w-full h-14 px-3 bg-transparent text-sm font-semibold text-slate-900 placeholder:text-slate-400 focus:outline-hidden"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={onClose}
            className="ml-2 px-2 py-1 text-[11px] font-bold text-slate-500 hover:text-slate-800 bg-slate-200/60 rounded-md transition cursor-pointer"
          >
            ESC
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-96 overflow-y-auto p-2 divide-y divide-slate-50">
          {filteredItems.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs">
              No pages found matching &quot;<span className="font-semibold text-slate-700">{query}</span>&quot;
            </div>
          ) : (
            filteredItems.map((item, index) => {
              const Icon = item.icon;
              const isSelected = index === selectedIndex;
              return (
                <div
                  key={item.id}
                  onClick={() => handleSelect(item.href)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl cursor-pointer transition ${
                    isSelected ? 'bg-blue-50 text-blue-900 font-medium' : 'hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border ${
                        isSelected
                          ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
                          : 'bg-slate-100 text-slate-600 border-slate-200'
                      }`}
                    >
                      <Icon className="w-4.5 h-4.5" />
                    </div>
                    <div className="flex flex-col min-w-0 text-left">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-900 truncate">{item.title}</span>
                        <span className="px-1.5 py-0.5 text-[9px] font-bold rounded-md bg-slate-100 text-slate-600 border border-slate-200 uppercase">
                          {item.category}
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-500 truncate mt-0.5">{item.description}</span>
                    </div>
                  </div>

                  <ArrowRight
                    className={`w-4 h-4 shrink-0 transition ${
                      isSelected ? 'text-blue-600 translate-x-0.5' : 'text-slate-300'
                    }`}
                  />
                </div>
              );
            })
          )}
        </div>

        {/* Footer shortcuts helper */}
        <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500 font-medium">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 text-[10px] bg-white border border-slate-200 rounded-md font-mono text-slate-700 shadow-2xs">
                ↑
              </kbd>
              <kbd className="px-1.5 py-0.5 text-[10px] bg-white border border-slate-200 rounded-md font-mono text-slate-700 shadow-2xs">
                ↓
              </kbd>
              Navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 text-[10px] bg-white border border-slate-200 rounded-md font-mono text-slate-700 shadow-2xs">
                ↵
              </kbd>
              Select
            </span>
          </div>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 text-[10px] bg-white border border-slate-200 rounded-md font-mono text-slate-700 shadow-2xs">
              ESC
            </kbd>
            Close
          </span>
        </div>
      </div>
    </div>
  );
}
