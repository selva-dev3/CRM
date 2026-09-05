'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Check,
  ChevronsUpDown,
  Loader2,
  RotateCcw,
  ShieldCheck,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { useDebouncedValue } from '@/hooks/use-debounced-value';
import { useAssignableRolesQuery, type RoleItem } from '@/lib/api/roles';
import { cn } from '@/lib/utils';

export interface RoleSearchComboboxProps {
  value?: string;
  onChange: (roleId: string) => void;
  id?: string;
  placeholder?: string;
  disabled?: boolean;
}

const SUPER_ADMIN_ROLE_NAMES = new Set(['super_admin', 'super admin', 'superadmin']);

const isSuperAdminRoleName = (value: string | undefined | null): boolean =>
  Boolean(value && SUPER_ADMIN_ROLE_NAMES.has(value.trim().toLowerCase()));

export function RoleSearchCombobox({
  value,
  onChange,
  id,
  placeholder = 'Search and select a role...',
  disabled = false,
}: RoleSearchComboboxProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedRoleName, setSelectedRoleName] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const { data: roles = [], isLoading, isError, refetch } = useAssignableRolesQuery(
    debouncedSearch.trim() || undefined
  );

  const displayedRoles = useMemo(
    () => roles.filter((role) => !isSuperAdminRoleName(role.name)),
    [roles]
  );
  const defaultAdminRole = useMemo(() => {
    if (displayedRoles.length === 0) return null;
    return (
      displayedRoles.find((role) => {
        const roleName = role.name.toLowerCase().trim();
        return roleName === 'admin' || roleName === 'administrator';
      }) ?? displayedRoles[0]
    );
  }, [displayedRoles]);

  useEffect(() => {
    if (!value && defaultAdminRole?.id) onChange(defaultAdminRole.id);
  }, [defaultAdminRole, onChange, value]);

  const selectedRole = displayedRoles.find((role) => role.id === value);
  const activeRoleName = selectedRole?.name || selectedRoleName;

  const selectRole = (role: RoleItem) => {
    onChange(role.id);
    setSelectedRoleName(role.name);
    setSearch('');
    setIsOpen(false);
  };

  const retryRoles = useCallback(() => {
    void refetch?.();
  }, [refetch]);

  return (
    <Popover
      open={isOpen}
      onOpenChange={(open) => {
        if (disabled) return;
        setIsOpen(open);
        if (open) setSearch('');
      }}
    >
      <PopoverTrigger asChild>
        <Button
          type="button"
          id={id}
          variant="outline"
          disabled={disabled}
          aria-label={activeRoleName || placeholder}
          className="h-10 w-full min-w-0 justify-between gap-2 border-[#E5E7EB] bg-white px-3 py-2 text-field shadow-saas-sm"
        >
          <span className="flex min-w-0 items-center gap-2">
            <ShieldCheck className="size-4 shrink-0 text-[#2563EB]" />
            <span
              className={cn(
                'truncate font-medium',
                activeRoleName ? 'text-[#111827]' : 'text-[#9CA3AF]'
              )}
            >
              {activeRoleName || placeholder}
            </span>
          </span>
          <ChevronsUpDown className="size-4 shrink-0 text-[#9CA3AF]" />
        </Button>
      </PopoverTrigger>

      <PopoverContent
        align="start"
        collisionPadding={8}
        className="w-[var(--radix-popover-trigger-width)] max-w-[calc(100vw-1rem)] p-0"
      >
        <Command shouldFilter={false}>
          <CommandInput
            aria-label="Search roles"
            placeholder="Search roles..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList className="max-h-[300px]">
            {isLoading ? (
              <div className="flex min-h-9 items-center justify-center gap-2 px-3 py-2 text-caption text-[#6B7280]">
                <Loader2 className="size-3.5 animate-spin" />
                Searching roles...
              </div>
            ) : isError ? (
              <div className="flex min-h-9 flex-col items-center justify-center gap-2 px-3 py-2 text-caption">
                <div className="flex items-center gap-2 text-[#DC2626]">
                  <AlertCircle className="size-3.5" />
                  Unable to load roles
                </div>
                <Button type="button" variant="outline" size="sm" onClick={retryRoles}>
                  <RotateCcw className="size-3" />
                  Try again
                </Button>
              </div>
            ) : (
              <>
                <CommandEmpty>No roles found</CommandEmpty>
                {displayedRoles.map((role) => (
                  <CommandItem
                    key={role.id}
                    value={role.name}
                    onSelect={() => selectRole(role)}
                    className="min-h-9 text-body font-medium"
                  >
                    <ShieldCheck className="size-4 shrink-0 text-[#6B7280]" />
                    <span className="truncate">{role.name}</span>
                    <Check
                      className={cn(
                        'ml-auto size-4 text-[#2563EB]',
                        value === role.id ? 'opacity-100' : 'opacity-0'
                      )}
                    />
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
