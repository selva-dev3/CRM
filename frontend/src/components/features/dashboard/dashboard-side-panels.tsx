import Link from 'next/link';
import { CheckCircle2, CheckSquare2, Mail, PhoneCall, Users, Video } from 'lucide-react';

import {
  Avatar,
  AvatarFallback,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui';
import type { ActivityItem } from '@/lib/api/activities';
import type { ContactItem } from '@/lib/api/contacts';
import type { ActivitiesSummary, TopPerformerItem } from '@/lib/api/dashboard';
import { cn } from '@/lib/utils';

import {
  DashboardSectionEmpty,
  DashboardSectionError,
  DashboardSectionSkeleton,
} from './dashboard-section-state';

function PanelHeader({ title, href }: { title: string; href: string }) {
  return (
    <CardHeader className="flex-row items-center justify-between border-b border-slate-100 px-4 py-3.5">
      <CardTitle className="text-sm font-semibold text-slate-950">{title}</CardTitle>
      <Link
        href={href}
        className="rounded text-xs font-medium text-blue-600 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        See all
      </Link>
    </CardHeader>
  );
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

function relativeDate(value?: string) {
  if (!value) return 'Recently added';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Recently added';
  const days = Math.max(0, Math.floor((Date.now() - date.getTime()) / 86_400_000));
  if (days === 0) return 'Today';
  if (days === 1) return '1 day ago';
  return `${days} days ago`;
}

export function RecentContactsCard({
  contacts,
  isLoading,
  isError,
  onRetry,
}: {
  contacts: ContactItem[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  return (
    <Card className="min-h-0 shadow-none">
      <PanelHeader title="Contacts" href="/contacts" />
      <CardContent className="p-2">
        {isLoading && <DashboardSectionSkeleton className="h-44" />}
        {isError && (
          <DashboardSectionError message="Recent contacts could not be loaded." onRetry={onRetry} />
        )}
        {!isLoading && !isError && contacts.length === 0 && (
          <DashboardSectionEmpty title="No contacts yet" description="New contacts will appear here." />
        )}
        {!isLoading && !isError && contacts.map((contact, index) => (
          <Link
            key={contact.id}
            href={`/contacts/${contact.id}`}
            className="group flex items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <span className="relative">
              <Avatar className="size-8">
                <AvatarFallback
                  className={cn(
                    'text-[10px] font-semibold',
                    index % 3 === 0 && 'bg-blue-50 text-blue-700',
                    index % 3 === 1 && 'bg-amber-50 text-amber-700',
                    index % 3 === 2 && 'bg-violet-50 text-violet-700',
                  )}
                >
                  {initials(contact.name)}
                </AvatarFallback>
              </Avatar>
              <span className="absolute -bottom-0.5 -right-0.5 size-2 rounded-full border-2 border-white bg-emerald-500" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-medium text-slate-900">{contact.name}</span>
              <span className="block truncate text-[10px] text-slate-500">
                {relativeDate(contact.created_at)}
              </span>
            </span>
            <span className="rounded-full bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-500 group-hover:bg-white group-hover:text-blue-600">
              View
            </span>
          </Link>
        ))}
      </CardContent>
    </Card>
  );
}

export function RecentActivityCard({
  activities,
  isLoading,
  isError,
  onRetry,
}: {
  activities: ActivityItem[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  return (
    <Card className="min-h-0 shadow-none">
      <PanelHeader title="Activity" href="/activities" />
      <CardContent className="p-2.5">
        {isLoading && <DashboardSectionSkeleton className="h-52" />}
        {isError && (
          <DashboardSectionError message="Recent activity could not be loaded." onRetry={onRetry} />
        )}
        {!isLoading && !isError && activities.length === 0 && (
          <DashboardSectionEmpty
            title="No recent activity"
            description="Updates across permitted modules will appear here."
          />
        )}
        {!isLoading && !isError && (
          <ol className="space-y-0.5">
            {activities.map((activity) => (
              <li key={activity.id}>
                <Link
                  href={activity.href}
                  className="group flex gap-2.5 rounded-lg px-1.5 py-2 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                >
                  <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white">
                    <CheckCircle2 className="size-3" aria-hidden="true" />
                  </span>
                  <span className="min-w-0">
                    <span className="line-clamp-2 block text-[11px] leading-4 text-slate-700">
                      <strong className="font-semibold text-slate-900 group-hover:text-blue-700">
                        {activity.action}
                      </strong>
                      {activity.description ? ` — ${activity.description}` : ''}
                    </span>
                    <time
                      className="mt-0.5 block text-[10px] text-slate-400"
                      dateTime={activity.occurred_at}
                    >
                      {new Intl.DateTimeFormat(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit',
                      }).format(new Date(activity.occurred_at))}
                    </time>
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

export function ActivitySummaryCard({
  data,
  isLoading,
  isError,
  onRetry,
}: {
  data?: ActivitiesSummary;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  const items = data ? [
    { label: 'Calls', value: data.calls_completed, icon: PhoneCall, color: 'text-blue-600' },
    { label: 'Emails', value: data.emails_sent, icon: Mail, color: 'text-indigo-600' },
    { label: 'Meetings', value: data.meetings_held, icon: Video, color: 'text-violet-600' },
    { label: 'Tasks', value: data.tasks_completed, icon: CheckSquare2, color: 'text-emerald-600' },
  ] : [];

  return (
    <Card className="shadow-none">
      <CardHeader className="border-b border-slate-100 px-4 py-3.5">
        <CardTitle className="text-sm">Activity summary</CardTitle>
        <p className="text-[11px] text-slate-500">{data?.period_label ?? 'Selected period'}</p>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading && <DashboardSectionSkeleton className="h-28 rounded-none" />}
        {isError && (
          <DashboardSectionError message="Activity totals could not be loaded." onRetry={onRetry} />
        )}
        {data && (
          <div className="grid grid-cols-2">
            {items.map(({ label, value, icon: Icon, color }, index) => (
              <div
                key={label}
                className={cn(
                  'flex items-center gap-2.5 border-slate-100 p-3.5',
                  index % 2 === 1 && 'border-l',
                  index > 1 && 'border-t',
                )}
              >
                <Icon className={cn('size-4', color)} aria-hidden="true" />
                <div>
                  <p className="text-[11px] text-slate-500">{label}</p>
                  <p className="text-base font-semibold text-slate-900 tabular-nums">{value}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function TopPerformersCard({
  performers,
  isLoading,
  isError,
  onRetry,
  formatCurrency,
}: {
  performers: TopPerformerItem[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  formatCurrency: (value: number) => string;
}) {
  return (
    <Card className="shadow-none">
      <CardHeader className="border-b border-slate-100 px-4 py-3.5">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Users className="size-4 text-amber-600" aria-hidden="true" />
          Top performers
        </CardTitle>
        <p className="text-[11px] text-slate-500">Closed-won revenue for this period</p>
      </CardHeader>
      <CardContent className="p-2">
        {isLoading && <DashboardSectionSkeleton className="h-40" />}
        {isError && (
          <DashboardSectionError message="Top performers could not be loaded." onRetry={onRetry} />
        )}
        {!isLoading && !isError && performers.length === 0 && (
          <DashboardSectionEmpty
            title="No won deals yet"
            description="Closed-won team performance will appear here."
          />
        )}
        {!isLoading && !isError && performers.length > 0 && (
          <div className="space-y-1">
            {performers.slice(0, 4).map((item, index) => (
              <div key={item.name} className="flex items-center gap-3 rounded-lg px-2.5 py-2">
                <span className="w-4 text-center text-[11px] font-semibold text-slate-400">{index + 1}</span>
                <Avatar className="size-8">
                  <AvatarFallback className="bg-amber-50 text-[11px] font-semibold text-amber-700">
                    {item.avatar}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-slate-900">{item.name}</p>
                  <p className="text-[11px] text-slate-500">{item.deals_count} won</p>
                </div>
                <span className="text-xs font-semibold text-emerald-700 tabular-nums">
                  {formatCurrency(item.revenue)}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
