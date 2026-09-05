'use client';

import type { ElementType } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowRight,
  BarChart3,
  Bell,
  Building2,
  Calendar,
  CalendarDays,
  CheckSquare,
  FileSpreadsheet,
  FileText,
  Kanban,
  LayoutDashboard,
  Mail,
  Package,
  PhoneCall,
  Receipt,
  Settings,
  ShieldCheck,
  StickyNote,
  UserCog,
  UserPlus,
  Users,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import {
  CommandDialog,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';

interface SearchItem {
  id: string;
  title: string;
  category: string;
  href: string;
  description: string;
  icon: ElementType;
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

  const handleSelect = (href: string) => {
    onClose();
    router.push(href);
  };

  return (
    <CommandDialog
      open={isOpen}
      onOpenChange={(open) => !open && onClose()}
      title="Search CRM"
      description="Search CRM pages, modules and settings"
      showCloseButton={false}
      className="top-16 max-w-xl translate-y-0 rounded-2xl border-slate-200 shadow-2xl sm:top-24"
    >
      <CommandInput placeholder="Search CRM pages, modules, settings..." />
      <CommandList className="max-h-96 p-2">
        <CommandEmpty>No matching CRM pages found.</CommandEmpty>
        {SEARCH_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <CommandItem
              key={item.id}
              value={item.title}
              keywords={[item.category, item.description]}
              onSelect={() => handleSelect(item.href)}
              className="group gap-3 rounded-xl px-3.5 py-2.5 data-[selected=true]:bg-blue-50 data-[selected=true]:text-blue-900"
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-slate-100 text-slate-600 group-data-[selected=true]:border-blue-600 group-data-[selected=true]:bg-blue-600 group-data-[selected=true]:text-white">
                <Icon className="size-4.5" />
              </span>
              <span className="min-w-0 flex-1 text-left">
                <span className="flex items-center gap-2">
                  <span className="truncate text-xs font-bold text-slate-900">{item.title}</span>
                  <Badge variant="secondary" className="h-5 text-[9px] uppercase">
                    {item.category}
                  </Badge>
                </span>
                <span className="mt-0.5 block truncate text-[11px] text-slate-500">
                  {item.description}
                </span>
              </span>
              <ArrowRight className="size-4 shrink-0 text-slate-300 group-data-[selected=true]:text-blue-600" />
            </CommandItem>
          );
        })}
      </CommandList>
      <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50 px-4 py-2.5 text-[11px] font-medium text-slate-500">
        <span>↑ ↓ Navigate · ↵ Select</span>
        <span>Esc Close</span>
      </div>
    </CommandDialog>
  );
}
