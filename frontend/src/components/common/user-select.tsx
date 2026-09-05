'use client';

import { useEffect, useMemo, useState } from 'react';
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
import { useUsersQuery, type UserItem } from '@/lib/api/users';
import { cn } from '@/lib/utils';

export interface UserSelectProps {
  value: string;
  onChange: (val: string) => void;
}

export function UserSelect({ value, onChange }: UserSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const { data: fetchedUsers = [], isLoading } = useUsersQuery(
    1,
    100,
    debouncedSearch.trim() || undefined
  );
  const selectedUser = useMemo(
    () => fetchedUsers.find((user: UserItem) => user.id === value),
    [fetchedUsers, value]
  );

  const selectUser = (userId: string) => {
    onChange(userId);
    setIsOpen(false);
    setSearch('');
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={isOpen}
          aria-label={
            selectedUser
              ? `${selectedUser.name} (${selectedUser.email || selectedUser.id})`
              : 'Select User Account'
          }
          className="h-9 w-full justify-between border-slate-200 px-3 text-xs font-medium"
        >
          <span className={cn('truncate', !selectedUser && 'text-slate-400')}>
            {selectedUser
              ? `${selectedUser.name} (${selectedUser.email || selectedUser.id})`
              : '-- Select User Account --'}
          </span>
          <ChevronsUpDown className="size-3.5 shrink-0 text-slate-400" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] p-0">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search user by name or email..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            {isLoading ? (
              <div className="flex items-center justify-center gap-2 px-2 py-3 text-xs font-medium text-slate-500">
                <Loader2 className="size-3.5 animate-spin text-blue-600" />
                Searching users via API...
              </div>
            ) : (
              <>
                <CommandEmpty>No matching users found</CommandEmpty>
                <CommandItem value="clear-user-selection" onSelect={() => selectUser('')}>
                  -- None / Clear Selection --
                </CommandItem>
                {fetchedUsers.map((user) => (
                  <CommandItem
                    key={user.id}
                    value={user.id}
                    onSelect={() => selectUser(user.id)}
                  >
                    <Check
                      className={cn(
                        'size-3.5',
                        value === user.id ? 'opacity-100' : 'opacity-0'
                      )}
                    />
                    <span className="min-w-0">
                      <span className="block truncate">{user.name}</span>
                      <span className="block truncate text-[10px] text-slate-400">
                        {user.email || user.id}
                      </span>
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
