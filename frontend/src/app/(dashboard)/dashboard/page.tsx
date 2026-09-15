import { Suspense } from 'react';
import { Skeleton } from '@/components/ui';
import { DashboardView } from '@/components/features/dashboard/dashboard-view';

export default function DashboardPage() {
  return <Suspense fallback={<Skeleton className="h-[70vh] w-full rounded-card" aria-label="Loading dashboard" />}><DashboardView /></Suspense>;
}
