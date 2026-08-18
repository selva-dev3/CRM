'use client';

import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AlertCircle, Check, ChevronDown, Loader2, RotateCcw, Search, ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useRolesQuery, type RoleItem } from '@/lib/api/roles';
import { useDebouncedValue } from '@/hooks/use-debounced-value';

export interface RoleSearchComboboxProps {
  value?: string;
  onChange: (roleId: string) => void;
  id?: string;
  placeholder?: string;
  disabled?: boolean;
}

interface PanelCoords {
  top: number;
  left: number;
  width: number;
  openUp: boolean;
  maxListHeight: number;
}

const LISTBOX_ID_PREFIX = 'role-search-listbox';
const OPTION_ID_PREFIX = 'role-search-option';
const PANEL_MAX_HEIGHT = 300;

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
  const [coords, setCoords] = useState<PanelCoords | null>(null);
  const debouncedSearch = useDebouncedValue(search, 300);

  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const optionRefs = useRef<(HTMLDivElement | null)[]>([]);

  const { data: roles = [], isLoading, isError, refetch } = useRolesQuery(
    debouncedSearch.trim() || undefined,
  );

  const selectedRole = useMemo(() => roles.find((r) => r.id === value), [roles, value]);
  const activeRoleName = selectedRole?.name || selectedRoleName;
  const effectiveHighlightedIndex = Math.min(highlightedIndex, Math.max(roles.length - 1, 0));
  const listboxId = `${LISTBOX_ID_PREFIX}-${id ?? 'role'}`;

  // Keep the portaled panel anchored to the trigger and clamped to the viewport.
  useLayoutEffect(() => {
    if (!isOpen) return;

    const updatePosition = () => {
      const trigger = containerRef.current;
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      // Match the trigger width but never exceed the viewport.
      const width = Math.max(0, Math.min(rect.width, viewportWidth - 16));
      const left = Math.max(8, Math.min(rect.left, viewportWidth - width - 8));

      const spaceBelow = viewportHeight - rect.bottom;
      const spaceAbove = rect.top;

      const PANEL_HEADER_HEIGHT = 56;
      const estimatedPanelHeight = PANEL_MAX_HEIGHT + PANEL_HEADER_HEIGHT;
      const openUp = spaceBelow < estimatedPanelHeight && spaceAbove > spaceBelow;

      let top: number;
      let maxListHeight: number;

      if (openUp) {
        top = rect.top - 4;
        const availableSpaceAbove = spaceAbove - 16 - PANEL_HEADER_HEIGHT;
        maxListHeight = Math.max(100, Math.min(PANEL_MAX_HEIGHT, availableSpaceAbove));
      } else {
        top = rect.bottom + 4;
        const availableSpaceBelow = spaceBelow - 16 - PANEL_HEADER_HEIGHT;
        maxListHeight = Math.max(100, Math.min(PANEL_MAX_HEIGHT, availableSpaceBelow));
      }

      setCoords({ top, left, width, openUp, maxListHeight });
    };

    updatePosition();
    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);
    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleMouseDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (containerRef.current?.contains(target)) return;
      if (panelRef.current?.contains(target)) return;
      setIsOpen(false);
    };
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
  }, [isOpen]);

  useEffect(() => {
    const el = optionRefs.current[effectiveHighlightedIndex];
    el?.scrollIntoView({ block: 'nearest' });
  }, [effectiveHighlightedIndex, isOpen, roles.length]);

  const openPanel = () => {
    if (disabled) return;
    setSearch('');
    setHighlightedIndex(0);
    setIsOpen(true);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const closePanel = () => {
    setIsOpen(false);
    setCoords(null);
    triggerRef.current?.focus();
  };

  const selectRole = (role: RoleItem) => {
    onChange(role.id);
    setSelectedRoleName(role.name);
    closePanel();
  };

  const retryRoles = useCallback(() => {
    refetch?.();
  }, [refetch]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      closePanel();
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
      const role = roles[effectiveHighlightedIndex];
      if (role) selectRole(role);
    }
  };

  return (
    <div ref={containerRef} className="relative w-full">
      <button
        ref={triggerRef}
        type="button"
        id={id}
        disabled={disabled}
        onClick={openPanel}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={isOpen ? listboxId : undefined}
        className="flex h-10 w-full min-w-0 items-center justify-between gap-2 rounded-input border border-[#E5E7EB] bg-white px-3 py-2 text-field shadow-saas-sm cursor-pointer focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className="flex min-w-0 items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-[#2563EB] shrink-0" />
          <span
            className={cn(
              'truncate font-medium',
              activeRoleName ? 'text-[#111827]' : 'text-[#9CA3AF]',
            )}
          >
            {activeRoleName || placeholder}
          </span>
        </span>
        <ChevronDown
          className={cn('w-4 h-4 text-[#9CA3AF] shrink-0 transition-transform', isOpen && 'rotate-180')}
        />
      </button>

      {isOpen && coords && typeof document !== 'undefined' && (
        createPortal(
          <div
            ref={panelRef}
            style={{
              top: coords.top,
              left: coords.left,
              width: coords.width,
              transform: coords.openUp ? 'translateY(-100%)' : undefined,
              zIndex: 99999,
            }}
            className="fixed max-w-[calc(100vw-1rem)] rounded-btn border border-[#E5E7EB] bg-white p-2 shadow-saas-lg animate-in fade-in-50 focus:outline-none"
          >
            <div className="relative mb-2">
              <Search className="pointer-events-none absolute left-3 top-1/2 w-4 h-4 -translate-y-1/2 text-[#9CA3AF]" />
              <Input
                ref={inputRef}
                type="text"
                role="combobox"
                aria-label="Search roles"
                aria-autocomplete="list"
                aria-expanded={isOpen}
                aria-controls={listboxId}
                aria-activedescendant={
                  roles.length > 0 ? `${OPTION_ID_PREFIX}-${effectiveHighlightedIndex}` : undefined
                }
                placeholder="Search roles..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setHighlightedIndex(0);
                }}
                onKeyDown={handleKeyDown}
                className="h-8 w-full pl-9 pr-3 text-caption"
              />
            </div>

            <div
              id={listboxId}
              role="listbox"
              aria-label="Available roles"
              style={{ maxHeight: `${coords.maxListHeight}px` }}
              className="space-y-0.5 overflow-y-auto overscroll-contain"
            >
              {isLoading ? (
                <div className="flex min-h-9 items-center justify-center gap-2 px-3 py-2 text-caption text-[#6B7280]">
                  <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                  Searching roles...
                </div>
              ) : isError ? (
                <div className="flex min-h-9 flex-col items-center justify-center gap-2 px-3 py-2 text-caption">
                  <div className="flex items-center gap-2 text-[#DC2626]">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                    Unable to load roles
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={retryRoles}
                    className="cursor-pointer text-caption"
                  >
                    <RotateCcw className="w-3 h-3" />
                    Try again
                  </Button>
                </div>
              ) : roles.length === 0 ? (
                <div className="flex min-h-9 items-center justify-center px-3 py-2 text-caption text-center text-[#6B7280]">
                  No roles found
                </div>
              ) : (
                roles.map((role, index) => (
                  <div
                    key={role.id}
                    id={`${OPTION_ID_PREFIX}-${index}`}
                    ref={(el) => {
                      optionRefs.current[index] = el;
                    }}
                    role="option"
                    aria-selected={value === role.id}
                    onClick={() => selectRole(role)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    className={cn(
                      'flex min-h-9 cursor-pointer items-center justify-between gap-2 rounded-btn px-2 py-1.5 text-body font-medium',
                      effectiveHighlightedIndex === index ? 'bg-[#F3F4F6]' : '',
                      value === role.id ? 'bg-[#2563EB]/10 text-[#2563EB]' : 'text-[#374151]',
                    )}
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-[#6B7280] shrink-0" />
                      <span className="truncate">{role.name}</span>
                    </span>
                    {value === role.id && <Check className="w-4 h-4 text-[#2563EB] shrink-0" />}
                  </div>
                ))
              )}
            </div>
          </div>,
          document.body,
        )
      )}
    </div>
  );
}
