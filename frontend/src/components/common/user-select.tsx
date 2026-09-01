'use client';

import { useEffect, useMemo, useState } from 'react';
import { Check, ChevronDown, Loader2, Search } from 'lucide-react';
import { useUsersQuery, type UserItem } from '@/lib/api/users';

export interface UserSelectProps {
  value: string;
  onChange: (val: string) => void;
}

export function UserSelect({ value, onChange }: UserSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Live GET /api/v1/users?page=1&limit=100&search=... API call on typing!
  const { data: fetchedUsers = [], isLoading } = useUsersQuery(1, 100, debouncedSearch.trim() || undefined);

  const selectedUser = useMemo(() => {
    return fetchedUsers.find((u: UserItem) => u.id === value);
  }, [fetchedUsers, value]);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-left text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center justify-between cursor-pointer"
      >
        <span className={selectedUser ? 'text-slate-900 font-semibold' : 'text-slate-400'}>
          {selectedUser ? `${selectedUser.name} (${selectedUser.email || selectedUser.id})` : '-- Select User Account --'}
        </span>
        <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
      </button>

      {isOpen && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-xl p-2 space-y-1.5 animate-in fade-in-50">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search user by name or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-8 pl-8 pr-2 text-xs rounded-md border border-slate-200 bg-slate-50 text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
            />
          </div>

          <div className="max-h-48 overflow-y-auto space-y-0.5">
            <button
              type="button"
              onClick={() => {
                onChange('');
                setIsOpen(false);
                setSearch('');
              }}
              className="w-full px-2 py-1.5 text-left text-xs text-slate-500 hover:bg-slate-100 rounded cursor-pointer"
            >
              -- None / Clear Selection --
            </button>
            {isLoading ? (
              <div className="px-2 py-3 text-xs text-slate-500 text-center flex items-center justify-center gap-2 font-medium">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-600" />
                <span>Searching users via API...</span>
              </div>
            ) : fetchedUsers.length === 0 ? (
              <div className="px-2 py-2 text-xs text-slate-400 text-center">No matching users found</div>
            ) : (
              fetchedUsers.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  onClick={() => {
                    onChange(u.id);
                    setIsOpen(false);
                    setSearch('');
                  }}
                  className={`w-full px-2 py-1.5 text-left text-xs rounded transition flex items-center justify-between cursor-pointer ${
                    value === u.id ? 'bg-blue-50 text-blue-700 font-bold' : 'text-slate-800 hover:bg-slate-100'
                  }`}
                >
                  <div className="flex flex-col">
                    <span>{u.name}</span>
                    <span className="text-[10px] text-slate-400 font-normal">{u.email || u.id}</span>
                  </div>
                  {value === u.id && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0" />}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
