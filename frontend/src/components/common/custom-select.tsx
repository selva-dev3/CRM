'use client';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

export interface CustomSelectOption {
  value: string;
  label: string;
}

export interface CustomSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: CustomSelectOption[];
  placeholder?: string;
  className?: string;
  id?: string;
  color?: 'blue' | 'indigo' | 'purple' | 'amber';
}

const FOCUS_COLORS = {
  blue: 'focus-visible:border-blue-500 focus-visible:ring-blue-500/20',
  indigo: 'focus-visible:border-indigo-500 focus-visible:ring-indigo-500/20',
  purple: 'focus-visible:border-purple-500 focus-visible:ring-purple-500/20',
  amber: 'focus-visible:border-amber-500 focus-visible:ring-amber-500/20',
} as const;

/** Compatibility wrapper retained for existing calendar/report/settings forms. */
export function CustomSelect({
  value,
  onChange,
  options,
  placeholder = 'Select an option',
  className,
  id,
  color = 'indigo',
}: CustomSelectProps) {
  return (
    <Select value={value || undefined} onValueChange={onChange}>
      <SelectTrigger
        id={id}
        className={cn(
          'h-9 w-full border-slate-300 bg-white px-3 text-xs font-semibold text-slate-900 shadow-xs',
          FOCUS_COLORS[color],
          className
        )}
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value} className="text-xs">
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
