'use client';

import React from 'react';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

const EMPTY_SELECT_VALUE = '__crm_empty_select_value__';

interface ResponsiveSelectProps {
  children: React.ReactNode;
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  className?: string;
  id?: string;
  name?: string;
  disabled?: boolean;
  required?: boolean;
  'aria-label'?: string;
}

interface SelectOption {
  disabled: boolean;
  key: React.Key;
  label: React.ReactNode;
  value: string;
}

function toInternalValue(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  return value === '' ? EMPTY_SELECT_VALUE : value;
}

function toExternalValue(value: string): string {
  return value === EMPTY_SELECT_VALUE ? '' : value;
}

function collectOptions(children: React.ReactNode, options: SelectOption[] = []): SelectOption[] {
  React.Children.forEach(children, (child) => {
    if (!React.isValidElement(child)) return;

    if (child.type === React.Fragment) {
      collectOptions((child.props as { children?: React.ReactNode }).children, options);
      return;
    }

    if (child.type !== 'option') return;

    const props = child.props as React.OptionHTMLAttributes<HTMLOptionElement>;
    const value = String(props.value ?? '');
    options.push({
      disabled: Boolean(props.disabled),
      key: child.key ?? `${value}-${options.length}`,
      label: props.children,
      value,
    });
  });

  return options;
}

/**
 * Mobile-safe adapter for the native selects that predate the shared Radix
 * design-system component. Existing option children remain source-compatible,
 * while the rendered popup is portaled and collision-aware.
 */
export function ResponsiveSelect({
  children,
  value,
  defaultValue,
  onValueChange,
  className,
  id,
  name,
  disabled,
  required,
  'aria-label': ariaLabel,
}: ResponsiveSelectProps): React.JSX.Element {
  const options = collectOptions(children);
  const emptyOption = options.find((option) => option.value === '');

  return (
    <Select
      value={toInternalValue(value)}
      defaultValue={toInternalValue(defaultValue)}
      onValueChange={(nextValue) => onValueChange?.(toExternalValue(nextValue))}
      name={name}
      disabled={disabled}
      required={required}
    >
      <SelectTrigger
        id={id}
        aria-label={ariaLabel}
        className={cn('min-h-11 w-full min-w-0 sm:min-h-9', className)}
      >
        <SelectValue placeholder={emptyOption?.label ?? 'Select an option'} />
      </SelectTrigger>
      <SelectContent
        position="popper"
        align="start"
        className="z-[70] w-[var(--radix-select-trigger-width)] max-w-[calc(100vw-1rem)]"
      >
        {options.map((option) => (
          <SelectItem
            key={option.key}
            value={toInternalValue(option.value) ?? EMPTY_SELECT_VALUE}
            disabled={option.disabled}
            className="min-h-11 sm:min-h-8"
          >
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export { EMPTY_SELECT_VALUE, toExternalValue, toInternalValue };
