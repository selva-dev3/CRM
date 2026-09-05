'use client';

import { useState } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import type { CompanyItem } from '@/lib/api/companies';
import { cn } from '@/lib/utils';

export interface SearchableCompanySelectProps {
  value: string;
  onChange: (val: string) => void;
  companies: Pick<CompanyItem, 'id' | 'name'>[];
}

export function SearchableCompanySelect({
  value,
  onChange,
  companies,
}: SearchableCompanySelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const selectedCompany = companies.find((company) => company.id === value);

  const selectCompany = (companyId: string) => {
    onChange(companyId);
    setIsOpen(false);
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={isOpen}
          aria-label={selectedCompany?.name ?? 'Select Company'}
          className="h-9 w-full justify-between border-slate-200 px-3 text-xs font-medium"
        >
          <span className={cn('truncate', !selectedCompany && 'text-slate-400')}>
            {selectedCompany?.name ?? '-- Select Company --'}
          </span>
          <ChevronsUpDown className="size-3.5 shrink-0 text-slate-400" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] p-0">
        <Command>
          <CommandInput placeholder="Search company by name..." />
          <CommandList>
            <CommandEmpty>No matching companies</CommandEmpty>
            <CommandItem value="clear-company-selection" onSelect={() => selectCompany('')}>
              -- None / Clear Selection --
            </CommandItem>
            {companies.map((company) => (
              <CommandItem
                key={company.id}
                value={company.name}
                onSelect={() => selectCompany(company.id)}
              >
                <Check
                  className={cn(
                    'size-3.5',
                    value === company.id ? 'opacity-100' : 'opacity-0'
                  )}
                />
                {company.name}
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
