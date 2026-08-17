'use client';

import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Bell, CheckCheck, Loader2, Inbox } from 'lucide-react';
import {
  useUnreadCountQuery,
  useNotificationsQuery,
  useMarkAllReadMutation,
  useMarkNotificationReadMutation,
  NotificationItem,
} from '@/lib/api/notifications';

const ENTITY_ROUTES: Record<string, string> = {
  lead: '/leads',
  contact: '/contacts',
  company: '/companies',
  deal: '/deals',
  task: '/tasks',
  meeting: '/meetings',
  invoice: '/invoices',
  product: '/products',
  quote: '/quotes',
  call: '/calls',
};

function notificationHref(n: NotificationItem): string | null {
  if (n.entity_type && n.entity_id && ENTITY_ROUTES[n.entity_type]) {
    return `${ENTITY_ROUTES[n.entity_type]}/${n.entity_id}`;
  }
  return null;
}

export function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const { data: unreadData } = useUnreadCountQuery();
  const { data: notifications = [], isLoading } = useNotificationsQuery({
    page: 1,
    limit: 8,
  });
  const markAllReadMutation = useMarkAllReadMutation();
  const markReadMutation = useMarkNotificationReadMutation();

  const unreadCount = unreadData?.unread_count ?? 0;
  const recent = notifications.slice(0, 8);

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEsc);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEsc);
    };
  }, [isOpen]);

  const handleMarkAllRead = async () => {
    try {
      await markAllReadMutation.mutateAsync();
    } catch {
      // best-effort: backend rejects silently; keep dropdown usable
    }
  };

  const handleMarkRead = async (id: string) => {
    try {
      await markReadMutation.mutateAsync(id);
    } catch {
      // best-effort
    }
  };

  const handleOpen = (n: NotificationItem) => {
    if (!n.is_read) {
      handleMarkRead(n.id);
    }
    const href = notificationHref(n);
    if (href) {
      router.push(href);
      setIsOpen(false);
    }
  };

  return (
    <div ref={containerRef} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        title="Notifications"
        aria-label="Notifications"
        aria-expanded={isOpen}
        className="p-2 rounded-xl transition cursor-pointer relative border flex items-center justify-center bg-slate-50 text-slate-700 hover:text-blue-600 hover:bg-slate-100 border-slate-200"
      >
        <Bell className="w-4.5 h-4.5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center ring-2 ring-white">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-[340px] sm:w-[380px] bg-white rounded-2xl border border-slate-200 shadow-xl z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Notifications</h3>
              <p className="text-[11px] text-slate-400">
                {unreadCount > 0 ? `${unreadCount} unread` : 'You are all caught up'}
              </p>
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleMarkAllRead}
                disabled={markAllReadMutation.isPending || unreadCount === 0}
                title="Mark all as read"
                className="p-1.5 rounded-lg text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 transition cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {markAllReadMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <CheckCheck className="w-4 h-4" />
                )}
              </button>
              <Link
                href="/notifications"
                onClick={() => setIsOpen(false)}
                className="px-2.5 py-1.5 rounded-lg text-[11px] font-semibold text-indigo-600 hover:bg-indigo-50 transition"
              >
                View all
              </Link>
            </div>
          </div>

          <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
            {isLoading ? (
              <div className="flex items-center justify-center py-10 text-slate-400 gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />
                <span className="text-xs font-medium">Loading notifications...</span>
              </div>
            ) : recent.length === 0 ? (
              <div className="text-center py-10 space-y-1.5">
                <Inbox className="w-8 h-8 text-slate-300 mx-auto" />
                <p className="text-xs font-semibold text-slate-500">No notifications</p>
                <p className="text-[11px] text-slate-400">New activity will appear here.</p>
              </div>
            ) : (
              recent.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleOpen(n)}
                  className={`w-full text-left px-4 py-3 transition flex items-start gap-3 cursor-pointer ${
                    !n.is_read ? 'bg-indigo-50/50 hover:bg-indigo-50' : 'hover:bg-slate-50'
                  }`}
                >
                  <span
                    className={`mt-1 h-2 w-2 rounded-full shrink-0 ${
                      !n.is_read ? 'bg-blue-600' : 'bg-slate-200'
                    }`}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs font-bold text-slate-900 truncate">
                      {n.title || 'System Notification'}
                    </span>
                    <span className="block text-[11px] text-slate-600 leading-relaxed line-clamp-2">
                      {n.message}
                    </span>
                    <span className="block text-[10px] text-slate-400 pt-0.5 font-mono">
                      {n.created_at ? n.created_at.substring(0, 16) : 'Just now'}
                    </span>
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}