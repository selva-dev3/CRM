'use client';

import { format } from 'date-fns';
import { CalendarIcon, Clock } from 'lucide-react';
import React, { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

interface PickerBaseProps {
  'aria-label'?: string;
  className?: string;
  disabled?: boolean;
  id?: string;
  placeholder?: string;
  required?: boolean;
}

interface DatePickerProps extends PickerBaseProps {
  value: string;
  onValueChange: (value: string) => void;
}

interface DateTimePickerProps extends PickerBaseProps {
  value: string;
  onValueChange: (value: string) => void;
}

function parseLocalDate(value: string): Date | undefined {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return undefined;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day);

  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return undefined;
  }

  return date;
}

function toDateValue(date: Date): string {
  return format(date, 'yyyy-MM-dd');
}

function getTimeValue(value: string): string {
  const match = /T(\d{2}):(\d{2})/.exec(value);
  return match ? `${match[1]}:${match[2]}` : '';
}

function formatDateTimeValue(value: string): string | null {
  const date = parseLocalDate(value);
  const time = getTimeValue(value);
  if (!date || !time) return null;

  const [hours, minutes] = time.split(':').map(Number);
  date.setHours(hours, minutes, 0, 0);
  return format(date, 'PPP p');
}

const triggerClassName =
  'min-h-11 w-full min-w-0 justify-start overflow-hidden text-left font-normal sm:min-h-9';

export function DatePicker({
  value,
  onValueChange,
  className,
  disabled,
  id,
  placeholder = 'Select a date',
  required,
  'aria-label': ariaLabel,
}: DatePickerProps): React.JSX.Element {
  const [open, setOpen] = useState(false);
  const selected = parseLocalDate(value);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          disabled={disabled}
          aria-label={ariaLabel}
          aria-required={required}
          className={cn(triggerClassName, !selected && 'text-muted-foreground', className)}
        >
          <CalendarIcon className="mr-2 size-4 shrink-0" />
          <span className="truncate">{selected ? format(selected, 'PPP') : placeholder}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="z-[70] w-auto max-w-[calc(100vw-1rem)] p-0"
      >
        <Calendar
          mode="single"
          selected={selected}
          defaultMonth={selected}
          onSelect={(date) => {
            if (!date) return;
            onValueChange(toDateValue(date));
            setOpen(false);
          }}
        />
        {selected && (
          <div className="border-t p-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="w-full"
              onClick={() => {
                onValueChange('');
                setOpen(false);
              }}
            >
              Clear date
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}

export function DateTimePicker({
  value,
  onValueChange,
  className,
  disabled,
  id,
  placeholder = 'Select date and time',
  required,
  'aria-label': ariaLabel,
}: DateTimePickerProps): React.JSX.Element {
  const selected = parseLocalDate(value);
  const selectedTime = getTimeValue(value);
  const [open, setOpen] = useState(false);
  const [draftDate, setDraftDate] = useState<Date | undefined>(selected);
  const [draftTime, setDraftTime] = useState(selectedTime);
  const displayValue = formatDateTimeValue(value);

  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      setDraftDate(selected);
      setDraftTime(selectedTime);
    }
    setOpen(nextOpen);
  };

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          disabled={disabled}
          aria-label={ariaLabel}
          aria-required={required}
          className={cn(triggerClassName, !displayValue && 'text-muted-foreground', className)}
        >
          <CalendarIcon className="mr-2 size-4 shrink-0" />
          <span className="truncate">{displayValue ?? placeholder}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="z-[70] w-auto max-w-[calc(100vw-1rem)] p-0"
      >
        <Calendar
          mode="single"
          selected={draftDate}
          defaultMonth={draftDate}
          onSelect={(date) => {
            setDraftDate(date);
            if (date && !draftTime) setDraftTime('09:00');
          }}
        />
        <div className="space-y-3 border-t p-3">
          <label htmlFor={`${id ?? 'date-time'}-time`} className="text-xs font-medium">
            Time
          </label>
          <div className="relative">
            <Clock className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id={`${id ?? 'date-time'}-time`}
              type="time"
              value={draftTime}
              onChange={(event) => setDraftTime(event.target.value)}
              className="min-h-11 pl-9 sm:min-h-9"
            />
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="flex-1"
              onClick={() => {
                onValueChange('');
                setOpen(false);
              }}
            >
              Clear
            </Button>
            <Button
              type="button"
              size="sm"
              className="flex-1"
              disabled={!draftDate || !draftTime}
              onClick={() => {
                if (!draftDate || !draftTime) return;
                onValueChange(`${toDateValue(draftDate)}T${draftTime}`);
                setOpen(false);
              }}
            >
              Apply
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export { formatDateTimeValue, getTimeValue, parseLocalDate, toDateValue };
