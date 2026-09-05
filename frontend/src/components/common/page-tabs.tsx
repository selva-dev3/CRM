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
  className,
  listClassName,
  triggerClassName,
}: PageTabsProps<TValue>) {
  return (
    <Tabs
      value={value}
      onValueChange={(nextValue) => onValueChange(nextValue as TValue)}
      className={cn('w-full overflow-x-auto', className)}
    >
      <TabsList
        variant={variant}
        className={cn('min-w-max justify-start', listClassName)}
      >
        {tabs.map((tab) => (
          <TabsTrigger
            key={tab.value}
            value={tab.value}
            className={cn('shrink-0 gap-2 whitespace-nowrap', triggerClassName)}
          >
            {tab.icon}
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
