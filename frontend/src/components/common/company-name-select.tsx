'use client';

import { useEffect, useState } from 'react';
import { Check, ChevronsUpDown, Loader2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';

import { companyKeys, fetchCompaniesApi } from '@/lib/api/companies';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import {
  Command,
  CommandEmpty,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Popover, PopoverAnchor, PopoverContent } from '@/components/ui/popover';

interface CompanyNameSelectProps {
  id: string;
  value: string;
  onChange: (value: string) => void;
  enabled?: boolean;
  disabled?: boolean;
  className?: string;
  'aria-invalid'?: boolean;
  'aria-describedby'?: string;
}

export function CompanyNameSelect({
  id,
  value,
  onChange,
  enabled = true,
  disabled = false,
  className,
  'aria-invalid': ariaInvalid,
  'aria-describedby': ariaDescribedBy,
}: CompanyNameSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(value.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [value]);

  const companies = useQuery({
    queryKey: companyKeys.list(1, 50, debouncedSearch || undefined),
    queryFn: () => fetchCompaniesApi(1, 50, debouncedSearch || undefined),
    enabled: enabled && isOpen,
    retry: false,
  });

  return (
    <Popover open={isOpen} onOpenChange={(open) => !disabled && setIsOpen(open)}>
      <PopoverAnchor asChild>
        <div className="relative">
          <Input
            id={id}
            role="combobox"
            aria-expanded={isOpen}
            aria-controls={`${id}-options`}
            aria-autocomplete="list"
            aria-invalid={ariaInvalid}
            aria-describedby={ariaDescribedBy}
            autoComplete="organization"
            value={value}
            disabled={disabled}
            onFocus={() => setIsOpen(true)}
            onChange={(event) => {
              onChange(event.target.value);
              setIsOpen(true);
            }}
            placeholder="Search or enter a company"
            className={cn('pr-9', className)}
          />
          <ChevronsUpDown className="pointer-events-none absolute right-3 top-1/2 size-3.5 -translate-y-1/2 text-slate-400" />
        </div>
      </PopoverAnchor>
      <PopoverContent
        align="start"
        className="w-[min(24rem,calc(100vw-2rem))] p-0 sm:w-[var(--radix-popover-anchor-width)]"
        onOpenAutoFocus={(event) => event.preventDefault()}
      >
        <Command shouldFilter={false}>
          <CommandList id={`${id}-options`}>
            {companies.isLoading ? (
              <div className="flex items-center justify-center gap-2 px-3 py-4 text-xs text-slate-500">
                <Loader2 className="size-3.5 animate-spin text-indigo-600" />
                Searching companies...
              </div>
            ) : companies.isError ? (
              <p className="px-3 py-4 text-xs text-rose-600" role="alert">
                Unable to load companies. You can still enter a company name.
              </p>
            ) : (
              <>
                <CommandEmpty>No matching companies</CommandEmpty>
                {(companies.data ?? []).map((company) => (
                  <CommandItem
                    key={company.id}
                    value={company.name}
                    onSelect={() => {
                      onChange(company.name);
                      setIsOpen(false);
                    }}
                  >
                    <Check className="mr-2 size-3.5 opacity-0" />
                    <span className="truncate">{company.name}</span>
                  </CommandItem>
                ))}
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
