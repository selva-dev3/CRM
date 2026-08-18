'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Check, ChevronDown, Loader2, Search, ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { useRolesQuery, type RoleItem } from '@/lib/api/roles';
import { useDebouncedValue } from '@/hooks/use-debounced-value';

export interface RoleSearchComboboxProps {
  value?: string;
  onChange: (roleId: string) => void;
  id?: string;
  placeholder?: string;
  disabled?: boolean;
}

export function RoleSearchCombobox({
  value,
  onChange,
  id,
  placeholder = 'Search and select a role...',
  disabled = false,
}: RoleSearchComboboxProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const [selectedRoleName, setSelectedRoleName] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: roles = [], isLoading, isError } = useRolesQuery(
    debouncedSearch.trim() || undefined,
  );

  const selectedRole = useMemo(() => roles.find((r) => r.id === value), [roles, value]);
  const activeRoleName = selectedRole?.name || selectedRoleName;

  useEffect(() => {
    if (!isOpen) return;
    const handleMouseDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
  }, [isOpen]);

  const openPanel = () => {
    if (disabled) return;
    setSearch('');
    setHighlightedIndex(0);
    setIsOpen(true);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const selectRole = (role: RoleItem) => {
    onChange(role.id);
    setSelectedRoleName(role.name);
    setIsOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setIsOpen(false);
      return;
    }
    if (roles.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((i) => Math.min(i + 1, roles.length - 1));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((i) => Math.max(i - 1, 0));
      return;
    }
    if (e.key === 'Enter' && isOpen) {
      e.preventDefault();
      const role = roles[highlightedIndex];
      if (role) selectRole(role);
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        id={id}
        disabled={disabled}
        onClick={openPanel}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        className="flex h-10 w-full items-center justify-between rounded-input border border-[#E5E7EB] bg-white px-3 py-2 text-field focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20 shadow-saas-sm cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
      >
        <div className="flex items-center gap-2 truncate">
          <ShieldCheck className="w-4 h-4 text-[#2563EB] shrink-0" />
          <span
            className={cn(
              'font-medium truncate',
              activeRoleName ? 'text-[#111827]' : 'text-[#9CA3AF]',
            )}
          >
            {activeRoleName || placeholder}
          </span>
        </div>
        <ChevronDown className="w-4 h-4 text-[#9CA3AF] shrink-0" />
      </button>

      {isOpen && (
        <div className="absolute z-50 left-0 right-0 mt-1 bg-white border border-[#E5E7EB] rounded-btn shadow-saas-lg p-2 space-y-2 animate-in fade-in-50">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-[#9CA3AF]" />
            <Input
              ref={inputRef}
              type="text"
              placeholder="Search roles..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setHighlightedIndex(0);
              }}
              onKeyDown={handleKeyDown}
              className="pl-8 text-caption h-8"
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={isOpen}
            />
          </div>

          <div className="space-y-0.5 max-h-36 overflow-y-auto" role="listbox">
            {isLoading ? (
              <div className="flex items-center justify-center gap-2 p-3 text-caption text-[#6B7280]">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Loading roles...
              </div>
            ) : isError ? (
              <div className="flex items-center justify-center gap-2 p-3 text-caption text-[#DC2626]">
                <AlertCircle className="w-3.5 h-3.5" />
                Unable to load roles
              </div>
            ) : roles.length === 0 ? (
              <div className="p-3 text-caption text-center text-[#6B7280]">
                No roles found
              </div>
            ) : (
              roles.map((role, index) => (
                <div
                  key={role.id}
                  role="option"
                  aria-selected={value === role.id}
                  onClick={() => selectRole(role)}
                  onMouseEnter={() => setHighlightedIndex(index)}
                  className={cn(
                    'flex items-center justify-between p-2 rounded-btn text-body font-medium cursor-pointer',
                    highlightedIndex === index ? 'bg-[#F3F4F6]' : '',
                    value === role.id ? 'bg-[#2563EB]/10 text-[#2563EB]' : 'text-[#374151]',
                  )}
                >
                  <div className="flex items-center gap-2 truncate">
                    <ShieldCheck className="w-4 h-4 text-[#6B7280] shrink-0" />
                    <span className="truncate">{role.name}</span>
                  </div>
                  {value === role.id && <Check className="w-4 h-4 text-[#2563EB] shrink-0" />}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}