'use client';

import type { ReactNode } from 'react';

import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';

export interface PageTab<TValue extends string> {
  value: TValue;
  label: ReactNode;
  icon?: ReactNode;
}

interface PageTabsProps<TValue extends string> {
  value: TValue;
  onValueChange: (value: TValue) => void;
  tabs: readonly PageTab<TValue>[];
  variant?: 'default' | 'line';
  /** Use the shared record-detail treatment for tabs that anchor a long profile page. */
  detail?: boolean;
  /** Keep the tab bar visible while the detail content scrolls. */
  sticky?: boolean;
  className?: string;
  listClassName?: string;
  triggerClassName?: string;
}

/** Controlled, scroll-safe shadcn tab navigation for CRM pages. */
export function PageTabs<TValue extends string>({
  value,
  onValueChange,
  tabs,
  variant = 'line',
  detail = false,
  sticky = false,
  className,
  listClassName,
  triggerClassName,
}: PageTabsProps<TValue>) {
  return (
    <Tabs
      value={value}
      onValueChange={(nextValue) => onValueChange(nextValue as TValue)}
      className={cn(
        'w-full overflow-x-auto',
        sticky && 'sticky top-0 z-20 -mx-4 bg-slate-50/95 px-4 py-2 backdrop-blur-sm sm:-mx-6 sm:px-6',
        className,
      )}
    >
      <TabsList
        variant={variant}
        className={cn(
          'min-w-max justify-start',
          detail && 'border-b border-slate-200 bg-transparent pb-0',
          listClassName,
        )}
      >
        {tabs.map((tab) => (
          <TabsTrigger
            key={tab.value}
            value={tab.value}
            className={cn(
              'shrink-0 gap-2 whitespace-nowrap',
              detail && 'text-button text-slate-500 data-[state=active]:text-blue-600',
              triggerClassName,
            )}
          >
            {tab.icon}
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
