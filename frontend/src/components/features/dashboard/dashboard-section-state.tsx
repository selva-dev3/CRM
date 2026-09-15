import { AlertCircle, Inbox } from 'lucide-react';
import { Button, Skeleton } from '@/components/ui';
import { cn } from '@/lib/utils';

export function DashboardSectionSkeleton({ className }: { className?: string }) { return <Skeleton className={cn('h-56 w-full rounded-card', className)} aria-hidden="true" />; }
export function DashboardSectionError({ message, onRetry }: { message: string; onRetry: () => void }) { return <div role="alert" className="flex min-h-44 flex-col items-center justify-center gap-3 px-5 text-center"><span className="flex size-10 items-center justify-center rounded-full bg-rose-50 text-rose-600"><AlertCircle className="size-5" aria-hidden="true" /></span><p className="max-w-sm text-sm font-medium text-slate-700">{message}</p><Button type="button" size="sm" variant="outline" onClick={onRetry}>Try again</Button></div>; }
export function DashboardSectionEmpty({ title, description }: { title: string; description: string }) { return <div className="flex min-h-44 flex-col items-center justify-center gap-2 px-5 text-center"><span className="flex size-10 items-center justify-center rounded-full bg-slate-100 text-slate-500"><Inbox className="size-5" aria-hidden="true" /></span><p className="text-sm font-semibold text-slate-900">{title}</p><p className="max-w-sm text-xs text-slate-500">{description}</p></div>; }
