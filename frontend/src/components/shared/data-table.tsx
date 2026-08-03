'use client';

import { Fragment, type ReactNode, useCallback, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Clock, ListFilter, MoreHorizontal, Pencil, Search, X } from 'lucide-react';

import { cn } from '@/lib/utils';
import { Avatar } from '@/components/shared/avatar';
import { EmptyState } from '@/components/shared/empty-state';
import { PermissionGate } from '@/components/shared/permission-gate';
import { Button } from '@/components/ui/button';

import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuCheckboxItem } from '../ui/dropdown-menu';

// ---------------------------------------------------------------------------
// Column definition
// ---------------------------------------------------------------------------
export interface DataTableColumn<TItem> {
  readonly id: string;
  readonly header: ReactNode;
  readonly cell: (item: TItem) => ReactNode;
  readonly className?: string;
  readonly enableHiding?: boolean;
}

// ---------------------------------------------------------------------------
// Row actions
// ---------------------------------------------------------------------------
export interface TableActionOption<TItem> {
  readonly label: string;
  readonly onClick: (item: TItem) => void;
  readonly variant?: 'default' | 'destructive';
  readonly icon?: ReactNode;
  readonly permission?: string;
}

// ---------------------------------------------------------------------------
// Filter definition for toolbar
// ---------------------------------------------------------------------------
export interface DataTableFilterOption {
  readonly label: string;
  readonly value: string;
  readonly options: readonly { readonly label: string; readonly value: string }[];
  readonly onChange: (value: string) => void;
}

// ---------------------------------------------------------------------------
// Pagination types
// ---------------------------------------------------------------------------
interface PaginationControlled {
  readonly pageIndex: number;
  readonly pageCount: number;
  readonly onPageChange: (pageIndex: number) => void;
  readonly totalRecords?: number;
}

interface PaginationUncontrolled {
  readonly pageSize?: number;
  readonly defaultPage?: number;
}

type DataTablePagination = PaginationControlled | PaginationUncontrolled;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface DataTableProps<TItem> {
  // Core
  readonly columns: readonly DataTableColumn<TItem>[];
  readonly data: readonly TItem[];
  readonly getRowKey: (item: TItem) => string;
  readonly emptyTitle: string;
  readonly emptyDescription: string;
  readonly onRowClick?: (item: TItem) => void;
  readonly className?: string;

  // Checkbox selection
  readonly showCheckbox?: boolean;
  readonly selectedIds?: ReadonlySet<string>;
  readonly onToggleRow?: (item: TItem, checked: boolean) => void;
  readonly onToggleAllRows?: (checked: boolean) => void;

  // Avatar leading
  readonly showAvatar?: boolean;
  readonly getAvatarData?: (item: TItem) => { name: string; color?: string };

  // Sub-text
  readonly showSubText?: boolean;
  readonly getSubText?: (item: TItem) => string | undefined;

  // Row actions
  readonly actionVariant?: 'menu' | 'inline';
  readonly actions?: readonly TableActionOption<TItem>[] | ((item: TItem) => readonly TableActionOption<TItem>[]);

  // Scroll
  readonly maxHeight?: string;

  // Toolbar
  readonly searchValue?: string;
  readonly onSearchChange?: (value: string) => void;
  readonly searchPlaceholder?: string;
  readonly filters?: readonly DataTableFilterOption[];
  readonly statusFilter?: {
    readonly value: string;
    readonly options: readonly { readonly label: string; readonly value: string }[];
    readonly onChange: (value: string) => void;
  };
  readonly sortOptions?: {
    readonly value: string;
    readonly options: readonly { readonly label: string; readonly value: string }[];
    readonly onChange: (value: string) => void;
  };
  readonly hasActiveFilters?: boolean;
  readonly onClearFilters?: () => void;
  readonly leftActions?: ReactNode;
  readonly toolbarActions?: ReactNode;

  // Pagination
  readonly pagination?: DataTablePagination;

  // Loading
  readonly isLoading?: boolean;
  readonly loadingRowCount?: number;

  // Expandable rows
  readonly expandableRow?: (item: TItem) => ReactNode;

  // Styling
  readonly transparent?: boolean;
  readonly padding?: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function isControlledPagination(p: DataTablePagination | undefined): p is PaginationControlled {
  return p !== undefined && 'pageIndex' in p;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function DataTable<TItem>({
  // Core
  columns,
  data,
  getRowKey,
  emptyTitle,
  emptyDescription,
  onRowClick,
  className,
  // Checkbox
  showCheckbox = false,
  selectedIds,
  onToggleRow,
  onToggleAllRows,
  // Avatar
  showAvatar = false,
  getAvatarData,
  // Sub-text
  showSubText = false,
  getSubText,
  // Row actions
  actionVariant = 'menu',
  actions,
  // Scroll
  maxHeight,
  // Toolbar
  searchValue,
  onSearchChange,
  searchPlaceholder = 'Search...',
  filters,
  statusFilter,
  sortOptions,
  hasActiveFilters,
  onClearFilters,
  leftActions,
  toolbarActions,
  // Pagination
  pagination,
  // Loading
  isLoading = false,
  loadingRowCount = 5,
  // Expandable rows
  expandableRow,
  // Styling
  transparent = false,
  padding = true,
}: DataTableProps<TItem>): React.JSX.Element {
  // --- Controlled vs uncontrolled pagination ---
  const [internalPageIndex, setInternalPageIndex] = useState(0);
  const [internalPageSize] = useState<number>(
    pagination && !isControlledPagination(pagination) ? pagination.pageSize ?? 20 : 20,
  );

  const pageIndex = isControlledPagination(pagination) ? pagination.pageIndex : internalPageIndex;
  const pageCount = isControlledPagination(pagination)
    ? pagination.pageCount
    : Math.max(1, Math.ceil(data.length / internalPageSize));
  const totalRecords = isControlledPagination(pagination)
    ? pagination.totalRecords
    : data.length;

  const handlePageChange = useCallback(
    (page: number) => {
      if (isControlledPagination(pagination)) {
        pagination.onPageChange(page);
      } else {
        setInternalPageIndex(page);
      }
    },
    [pagination],
  );

  // --- Paginate data in uncontrolled mode ---
  const displayData = useMemo(() => {
    if (isControlledPagination(pagination) || !pagination) {
      return data;
    }
    const start = pageIndex * internalPageSize;
    return data.slice(start, start + internalPageSize);
  }, [data, pagination, pageIndex, internalPageSize]);

  // --- Column visibility ---
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(new Set());
  const toggleColumn = useCallback((columnId: string) => {
    setHiddenColumns((prev) => {
      const next = new Set(prev);
      if (next.has(columnId)) {
        next.delete(columnId);
      } else {
        next.add(columnId);
      }
      return next;
    });
  }, []);
  const visibleColumns = useMemo(
    () => columns.filter((col) => !hiddenColumns.has(col.id)),
    [columns, hiddenColumns],
  );
  const hasHideableColumns = useMemo(
    () => columns.some((col) => col.enableHiding),
    [columns],
  );

  // --- Expanded rows ---
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const toggleRowExpanded = useCallback((rowKey: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(rowKey)) {
        next.delete(rowKey);
      } else {
        next.add(rowKey);
      }
      return next;
    });
  }, []);

  // --- Selection helpers ---
  const visibleRowKeys = useMemo(() => displayData.map(getRowKey), [displayData, getRowKey]);
  const selectedVisibleCount = useMemo(
    () => visibleRowKeys.filter((key) => selectedIds?.has(key)).length,
    [visibleRowKeys, selectedIds],
  );
  const allVisibleSelected = displayData.length > 0 && selectedVisibleCount === displayData.length;
  const someVisibleSelected = selectedVisibleCount > 0 && !allVisibleSelected;

  // --- Toolbar active state ---
  const hasToolbar =
    searchValue !== undefined ||
    filters ||
    statusFilter ||
    sortOptions ||
    leftActions ||
    toolbarActions;

  // --- Loading state ---
  if (isLoading) {
    return (
      <div className={cn(!transparent && 'rounded-xl border border-slate-200 bg-white shadow-xs', className)}>
        {hasToolbar && <DataTableToolbarSkeleton />}
        <div className={cn(padding && 'p-2')}>
          <Table>
            <TableHeader>
              <TableRow>
                {showCheckbox && <TableHead className="w-10 px-4" />}
                {columns.map((col) => (
                  <TableHead key={col.id} className={col.className}>
                    {col.header}
                  </TableHead>
                ))}
                {expandableRow && <TableHead className="w-10 px-4" />}
                {actions && <TableHead className="w-[80px] px-4" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: loadingRowCount }).map((_, idx) => (
                <TableRow key={idx}>
                  {showCheckbox && (
                    <TableCell className="w-10 px-4">
                      <Skeleton className="h-4 w-4" />
                    </TableCell>
                  )}
                  {columns.map((col) => (
                    <TableCell key={col.id} className={col.className}>
                      <Skeleton className="h-4 w-full max-w-32" />
                    </TableCell>
                  ))}
                  {expandableRow && <TableCell className="w-10 px-4" />}
                  {actions && (
                    <TableCell className="w-[80px] px-4 text-center">
                      <Skeleton className="h-8 w-8 mx-auto rounded-md" />
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    );
  }

  // --- Empty state ---
  if (displayData.length === 0) {
    return (
      <div className={cn(!transparent && 'rounded-xl border border-slate-200 bg-white shadow-xs', className)}>
        {hasToolbar && (
          <DataTableToolbar
            searchValue={searchValue}
            onSearchChange={onSearchChange}
            searchPlaceholder={searchPlaceholder}
            filters={filters}
            statusFilter={statusFilter}
            sortOptions={sortOptions}
            hasActiveFilters={hasActiveFilters}
            onClearFilters={onClearFilters}
            leftActions={leftActions}
            toolbarActions={toolbarActions}
            hasHideableColumns={hasHideableColumns}
            columns={columns}
            hiddenColumns={hiddenColumns}
            onToggleColumn={toggleColumn}
          />
        )}
        <div className={cn(padding && 'p-6')}>
          <EmptyState title={emptyTitle} description={emptyDescription} />
        </div>
      </div>
    );
  }

  return (
    <div className={cn(!transparent && 'rounded-xl border border-slate-200 bg-white shadow-xs', className)}>
      {hasToolbar && (
        <DataTableToolbar
          searchValue={searchValue}
          onSearchChange={onSearchChange}
          searchPlaceholder={searchPlaceholder}
          filters={filters}
          statusFilter={statusFilter}
          sortOptions={sortOptions}
          hasActiveFilters={hasActiveFilters}
          onClearFilters={onClearFilters}
          leftActions={leftActions}
          toolbarActions={toolbarActions}
          hasHideableColumns={hasHideableColumns}
          columns={columns}
          hiddenColumns={hiddenColumns}
          onToggleColumn={toggleColumn}
        />
      )}

      <div
        className={cn(
          'overflow-x-auto min-h-[260px] pb-12',
          maxHeight ? 'overflow-y-auto' : undefined,
          '[&>[data-slot=table-container]]:contents',
        )}
        style={maxHeight ? { maxHeight } : undefined}
      >
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-slate-50 border-b border-slate-200">
            <TableRow>
              {showCheckbox && (
                <TableHead className="w-10 px-4">
                  <input
                    type="checkbox"
                    checked={allVisibleSelected}
                    ref={(node) => {
                      if (node) {
                        node.indeterminate = someVisibleSelected;
                      }
                    }}
                    onChange={(event: React.ChangeEvent<HTMLInputElement>) => onToggleAllRows?.(event.target.checked)}
                    aria-label="Select all rows"
                  />
                </TableHead>
              )}
              {expandableRow && <TableHead className="w-10 px-4" aria-label="Expand row" />}
              {visibleColumns.map((column) => (
                <TableHead key={column.id} className={column.className}>
                  {column.header}
                </TableHead>
              ))}
              {actions && (
                <TableHead className={cn('px-4', actionVariant === 'inline' ? 'w-[100px] text-right' : 'w-[80px] text-center')}>
                  {actionVariant === 'menu' ? 'Actions' : ''}
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayData.map((item) => {
              const rowKey = getRowKey(item);
              const isExpanded = expandedRows.has(rowKey);

              return (
                <Fragment key={rowKey}>
                  <TableRow
                    tabIndex={onRowClick ? 0 : undefined}
                    className={cn(
                      onRowClick ? 'cursor-pointer hover:bg-slate-50' : undefined,
                    )}
                    onClick={() => onRowClick?.(item)}
                    onKeyDown={(event: React.KeyboardEvent<HTMLTableRowElement>) => {
                      if (!onRowClick || (event.key !== 'Enter' && event.key !== ' ')) {
                        return;
                      }
                      event.preventDefault();
                      onRowClick(item);
                    }}
                  >
                    {showCheckbox && (
                      <TableCell className="w-10 px-4">
                        <input
                          type="checkbox"
                          checked={selectedIds?.has(rowKey) ?? false}
                          onClick={(event: React.MouseEvent<HTMLInputElement>) => event.stopPropagation()}
                          onChange={(event: React.ChangeEvent<HTMLInputElement>) => onToggleRow?.(item, event.target.checked)}
                          aria-label="Select row"
                        />
                      </TableCell>
                    )}
                    {expandableRow && (
                      <TableCell className="w-10 px-4">
                        <button
                          type="button"
                          onClick={(e: React.MouseEvent) => {
                            e.stopPropagation();
                            toggleRowExpanded(rowKey);
                          }}
                          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition"
                          aria-label={isExpanded ? 'Collapse row' : 'Expand row'}
                          aria-expanded={isExpanded}
                        >
                          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </button>
                      </TableCell>
                    )}
                    {visibleColumns.map((column, colIndex) => {
                      let cellContent = column.cell(item);

                      if (colIndex === 0) {
                        const avatarData = showAvatar && getAvatarData ? getAvatarData(item) : null;
                        const subText = showSubText && getSubText ? getSubText(item) : null;

                        if (avatarData || subText) {
                          cellContent = (
                            <div className="flex items-center gap-2.5">
                              {avatarData && (
                                <Avatar name={avatarData.name} color={avatarData.color} size="md" />
                              )}
                              <div className="min-w-0">
                                <div className="text-xs font-bold text-slate-900">{cellContent}</div>
                                {subText && (
                                  <div className="mt-0.5 block max-w-lg truncate text-[11px] font-medium text-slate-500">
                                    {subText}
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        }
                      }

                      return (
                        <TableCell key={`${rowKey}-${column.id}`} className={column.className}>
                          {cellContent}
                        </TableCell>
                      );
                    })}
                    {(() => {
                      const resolvedActions = typeof actions === 'function' ? actions(item) : actions;
                      if (!resolvedActions || resolvedActions.length === 0) return null;
                      return (
                        <TableCell className={cn('px-4', actionVariant === 'inline' ? 'w-[100px] text-right' : 'w-[80px] text-center')}>
                          {actionVariant === 'menu' ? (
                            <DropdownMenu>
                              <DropdownMenuTrigger
                                className="h-8 w-8 p-0 border-0 bg-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg cursor-pointer"
                                onClick={(e: React.MouseEvent) => e.stopPropagation()}
                              >
                                <MoreHorizontal className="h-4 w-4 mx-auto" />
                                <span className="sr-only">Open menu</span>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-36">
                                {resolvedActions.map((action) => (
                                  <PermissionGate key={action.label} permission={action.permission}>
                                    <DropdownMenuItem
                                      onClick={(e: React.MouseEvent) => {
                                        e.stopPropagation();
                                        action.onClick(item);
                                      }}
                                    >
                                      {action.icon}
                                      <span>{action.label}</span>
                                    </DropdownMenuItem>
                                  </PermissionGate>
                                ))}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          ) : (
                            <div className="flex justify-end gap-1">
                              {resolvedActions.map((action) => (
                                <PermissionGate key={action.label} permission={action.permission}>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={(e: React.MouseEvent) => {
                                      e.stopPropagation();
                                      action.onClick(item);
                                    }}
                                    className="h-8 px-2 text-xs font-bold text-slate-700 hover:text-slate-900 hover:bg-slate-100"
                                  >
                                    {action.icon ? action.icon : <Pencil className="h-3.5 w-3.5 mr-1" />}
                                    {action.label}
                                  </Button>
                                </PermissionGate>
                              ))}
                            </div>
                          )}
                        </TableCell>
                      );
                    })()}
                  </TableRow>
                  {isExpanded && expandableRow && (
                    <TableRow key={`${rowKey}-expanded`}>
                      <TableCell
                        colSpan={
                          (showCheckbox ? 1 : 0) +
                          1 +
                          visibleColumns.length +
                          (actions ? 1 : 0)
                        }
                        className="bg-slate-50/70 p-4 border-b border-slate-200"
                      >
                        {expandableRow(item)}
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Pagination footer */}
      {pagination && pageCount > 1 && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-6 py-4 text-xs font-bold text-slate-700">
          <span>
            Page {pageIndex + 1} of {pageCount}
            {totalRecords !== undefined && ` · ${totalRecords} records`}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pageIndex <= 0}
              onClick={() => handlePageChange(pageIndex - 1)}
              className="border-slate-300 text-slate-900 font-bold hover:bg-slate-100 text-xs"
            >
              <ChevronRight className="h-4 w-4 rotate-180 mr-1" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={pageIndex >= pageCount - 1}
              onClick={() => handlePageChange(pageIndex + 1)}
              className="border-slate-300 text-slate-900 font-bold hover:bg-slate-100 text-xs"
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* Uncontrolled pagination count footer */}
      {pagination && !isControlledPagination(pagination) && pageCount <= 1 && totalRecords !== undefined && totalRecords > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-6 py-4 text-xs font-bold text-slate-700">
          <span>{totalRecords} records</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toolbar component
// ---------------------------------------------------------------------------
interface DataTableToolbarProps {
  readonly searchValue?: string;
  readonly onSearchChange?: (value: string) => void;
  readonly searchPlaceholder: string;
  readonly filters?: readonly DataTableFilterOption[];
  readonly statusFilter?: {
    readonly value: string;
    readonly options: readonly { readonly label: string; readonly value: string }[];
    readonly onChange: (value: string) => void;
  };
  readonly sortOptions?: {
    readonly value: string;
    readonly options: readonly { readonly label: string; readonly value: string }[];
    readonly onChange: (value: string) => void;
  };
  readonly hasActiveFilters?: boolean;
  readonly onClearFilters?: () => void;
  readonly leftActions?: ReactNode;
  readonly toolbarActions?: ReactNode;
  readonly hasHideableColumns: boolean;
  readonly columns: readonly { readonly id: string; readonly header: ReactNode; readonly enableHiding?: boolean }[];
  readonly hiddenColumns: ReadonlySet<string>;
  readonly onToggleColumn: (columnId: string) => void;
}

function DataTableToolbar({
  searchValue,
  onSearchChange,
  searchPlaceholder,
  filters,
  statusFilter,
  sortOptions,
  hasActiveFilters,
  onClearFilters,
  leftActions,
  toolbarActions,
  hasHideableColumns,
  columns,
  hiddenColumns,
  onToggleColumn,
}: DataTableToolbarProps): React.JSX.Element {
  return (
    <div className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-4 py-3">
      {leftActions && <div className="flex items-center gap-2">{leftActions}</div>}

      {onSearchChange && (
        <div className="relative min-w-0 flex-1 w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <Input
            type="text"
            value={searchValue ?? ''}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            className="h-9 w-full pl-8 pr-8 text-xs font-bold bg-slate-50 border-slate-300 text-slate-900 placeholder:text-slate-500"
          />
          {searchValue && (
            <button
              type="button"
              onClick={() => onSearchChange('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 flex h-5 w-5 items-center justify-center rounded-full text-slate-500 hover:text-slate-900"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      )}

      {filters?.map((filter) => (
        <DropdownMenu key={filter.value}>
          <DropdownMenuTrigger className="h-9 px-3 py-1.5 border border-slate-300 bg-slate-50 hover:bg-slate-100 rounded-lg text-xs font-bold text-slate-900 inline-flex items-center gap-1.5 cursor-pointer">
            <ListFilter className="h-3.5 w-3.5 text-slate-500" />
            <span>{filter.label}</span>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-44">
            {filter.options.map((option) => (
              <DropdownMenuItem
                key={option.value}
                onClick={() => filter.onChange(option.value)}
                className="cursor-pointer text-xs font-bold text-slate-900"
              >
                {option.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      ))}

      {statusFilter && (
        <DropdownMenu>
          <DropdownMenuTrigger className="h-9 px-3 py-1.5 border border-slate-300 bg-slate-50 hover:bg-slate-100 rounded-lg text-xs font-bold text-slate-900 inline-flex items-center gap-1.5 cursor-pointer">
            <Clock className="h-3.5 w-3.5 text-slate-500" />
            <span className="font-extrabold capitalize">{statusFilter.value || 'Status'}</span>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-40">
            <DropdownMenuRadioGroup
              value={statusFilter.value}
              onValueChange={statusFilter.onChange}
            >
              {statusFilter.options.map((option) => (
                <DropdownMenuRadioItem
                  key={option.value}
                  value={option.value}
                  className="cursor-pointer text-xs font-bold capitalize"
                >
                  {option.label}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      {sortOptions && (
        <DropdownMenu>
          <DropdownMenuTrigger className="h-9 px-3 py-1.5 border border-slate-300 bg-slate-50 hover:bg-slate-100 rounded-lg text-xs font-bold text-slate-900 inline-flex items-center gap-1.5 cursor-pointer">
            <ChevronDown className="h-3.5 w-3.5 text-slate-500" />
            <span>{sortOptions.options.find((o) => o.value === sortOptions.value)?.label ?? 'Sort'}</span>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-40">
            <DropdownMenuRadioGroup
              value={sortOptions.value}
              onValueChange={sortOptions.onChange}
            >
              {sortOptions.options.map((option) => (
                <DropdownMenuRadioItem
                  key={option.value}
                  value={option.value}
                  className="cursor-pointer text-xs font-bold"
                >
                  {option.label}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      <div className="flex-1" />

      {hasActiveFilters && onClearFilters && (
        <Button variant="ghost" size="sm" className="h-9 gap-1.5 text-xs font-bold text-rose-600 hover:bg-rose-50" onClick={onClearFilters}>
          <X className="h-3.5 w-3.5" />
          Clear filters
        </Button>
      )}

      {hasHideableColumns && (
        <DropdownMenu>
          <DropdownMenuTrigger className="h-9 px-3 py-1.5 border border-slate-300 bg-slate-50 hover:bg-slate-100 rounded-lg text-xs font-bold text-slate-900 inline-flex items-center gap-1.5 cursor-pointer">
            <ListFilter className="h-3.5 w-3.5" />
            <span>Columns</span>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-44">
            <DropdownMenuLabel className="text-xs font-bold text-slate-900">Toggle columns</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {columns.filter((col) => col.enableHiding).map((col) => (
              <DropdownMenuCheckboxItem
                key={col.id}
                checked={!hiddenColumns.has(col.id)}
                onClick={() => onToggleColumn(col.id)}
                className="cursor-pointer text-xs font-bold text-slate-900"
              >
                {typeof col.header === 'string' ? col.header : col.id}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      {toolbarActions && <div className="flex items-center gap-2">{toolbarActions}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toolbar skeleton
// ---------------------------------------------------------------------------
function DataTableToolbarSkeleton(): React.JSX.Element {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-4 py-3">
      <Skeleton className="h-9 w-64 rounded-md" />
      <Skeleton className="h-9 w-24 rounded-md" />
      <Skeleton className="h-9 w-24 rounded-md" />
      <div className="flex-1" />
      <Skeleton className="h-9 w-24 rounded-md" />
    </div>
  );
}
