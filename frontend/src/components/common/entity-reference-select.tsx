'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Check, ChevronsUpDown, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { fetchCompaniesApi } from '@/lib/api/companies';
import { fetchContactsApi } from '@/lib/api/contacts';
import { fetchDealsApi } from '@/lib/api/deals';
import { fetchLeadsApi } from '@/lib/api/leads';
import { useHasPermission } from '@/hooks/use-has-permission';
import { PERMISSIONS, type PermissionKey } from '@/lib/permissions';
import { cn } from '@/lib/utils';

export type EntityReferenceType = 'Lead' | 'Contact' | 'Deal' | 'Company';

export const ENTITY_REFERENCE_TYPES: ReadonlyArray<{
  value: EntityReferenceType;
  readPermission: PermissionKey;
}> = [
  { value: 'Lead', readPermission: PERMISSIONS.LEADS.READ },
  { value: 'Contact', readPermission: PERMISSIONS.CONTACTS.READ },
  { value: 'Deal', readPermission: PERMISSIONS.DEALS.READ },
  { value: 'Company', readPermission: PERMISSIONS.COMPANIES.READ },
];

interface EntityOption {
  id: string;
  label: string;
  description?: string;
}

export interface EntityReferenceSelectProps {
  entityType: EntityReferenceType;
  value: string;
  onChange: (id: string, label: string) => void;
  selectedLabel?: string;
}

async function fetchEntityOptions(
  entityType: EntityReferenceType,
  search?: string,
): Promise<EntityOption[]> {
  if (entityType === 'Lead') {
    const page = await fetchLeadsApi({ page: 1, limit: 50, search });
    return page.items.map((lead) => ({
      id: lead.id,
      label: lead.contact_name || lead.title,
      description: [lead.title, lead.company].filter(Boolean).join(' — '),
    }));
  }
  if (entityType === 'Contact') {
    const contacts = await fetchContactsApi(1, 50, search);
    return contacts.map((contact) => ({
      id: contact.id,
      label: contact.name,
      description: contact.email,
    }));
  }
  if (entityType === 'Deal') {
    const deals = await fetchDealsApi(1, 50, undefined, search);
    return deals.map((deal) => ({
      id: deal.id,
      label: deal.title,
      description: deal.stage,
    }));
  }

  const companies = await fetchCompaniesApi(1, 50, search);
  return companies.map((company) => ({
    id: company.id,
    label: company.name,
    description: company.domain,
  }));
}

export function EntityReferenceSelect({
  entityType,
  value,
  onChange,
  selectedLabel,
}: EntityReferenceSelectProps): React.JSX.Element {
  const { hasPermission } = useHasPermission();
  const requiredPermission = ENTITY_REFERENCE_TYPES.find(
    (option) => option.value === entityType,
  )!.readPermission;
  const canReadEntity = hasPermission(requiredPermission);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [search]);

  const { data: options = [], isLoading, isError } = useQuery({
    queryKey: ['note-entity-options', entityType, debouncedSearch],
    queryFn: () => fetchEntityOptions(entityType, debouncedSearch || undefined),
    enabled: open && canReadEntity,
    staleTime: 60_000,
  });
  const selected = useMemo(
    () => options.find((option) => option.id === value),
    [options, value],
  );
  const displayLabel = selected?.label || selectedLabel;

  return (
    <Popover open={open} onOpenChange={(nextOpen) => {
      setOpen(nextOpen);
      if (!nextOpen) setSearch('');
    }}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label={`Select ${entityType}`}
          disabled={!canReadEntity}
          className="h-10 w-full justify-between border-slate-300 bg-slate-50 px-3.5 text-sm font-normal"
        >
          <span className={cn('truncate', !displayLabel && 'text-slate-400')}>
            {displayLabel || (
              canReadEntity
                ? `Select a ${entityType.toLowerCase()}`
                : `No permission to view ${entityType.toLowerCase()}s`
            )}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 text-slate-400" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        collisionPadding={8}
        className="z-[80] w-[var(--radix-popover-trigger-width)] p-0"
      >
        <Command shouldFilter={false}>
          <CommandInput
            placeholder={`Search ${entityType.toLowerCase()}s...`}
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            {isLoading ? (
              <div className="flex items-center justify-center gap-2 px-3 py-4 text-xs text-slate-500">
                <Loader2 className="size-4 animate-spin" /> Loading {entityType.toLowerCase()}s...
              </div>
            ) : isError ? (
              <div className="px-3 py-4 text-center text-xs text-rose-600">
                Failed to load {entityType.toLowerCase()}s.
              </div>
            ) : (
              <>
                <CommandEmpty>No matching {entityType.toLowerCase()} found.</CommandEmpty>
                {options.map((option) => (
                  <CommandItem
                    key={option.id}
                    value={option.id}
                    onSelect={() => {
                      onChange(option.id, option.label);
                      setOpen(false);
                      setSearch('');
                    }}
                  >
                    <Check className={cn('size-4', value === option.id ? 'opacity-100' : 'opacity-0')} />
                    <span className="min-w-0">
                      <span className="block truncate">{option.label}</span>
                      {option.description && (
                        <span className="block truncate text-[11px] text-slate-400">
                          {option.description}
                        </span>
                      )}
                    </span>
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
