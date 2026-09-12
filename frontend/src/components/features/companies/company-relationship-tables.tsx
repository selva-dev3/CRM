'use client';

import type { MouseEvent } from 'react';

import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { Button } from '@/components/ui/button';
import type { CompanyContactItem } from '@/lib/api/companies';
import type { DealItem } from '@/lib/api/deals';
import type { DocumentItem } from '@/lib/api/documents';
import type { InvoiceItem } from '@/lib/api/invoices';
import type { NoteItem } from '@/lib/api/notes';
import type { QuoteItem } from '@/lib/api/quotes';
import { formatDate, formatDateTime } from '@/lib/formatters/date';
import { formatInvoiceMoney } from '@/lib/formatters/invoice';

interface RelationshipTableProps<TItem> {
  readonly data: readonly TItem[];
  readonly isLoading: boolean;
  readonly onRowClick?: (item: TItem) => void;
  readonly pagination?: {
    pageIndex: number;
    pageCount: number;
    totalRecords: number;
    onPageChange: (pageIndex: number) => void;
  };
}

interface RelationshipErrorProps {
  readonly resourceName: string;
  readonly onRetry: () => void;
  readonly unavailable?: boolean;
}

const contactColumns: readonly DataTableColumn<CompanyContactItem>[] = [
  {
    id: 'name',
    header: 'Contact',
    cell: (contact) =>
      contact.name?.trim() ||
      `${contact.first_name ?? ''} ${contact.last_name ?? ''}`.trim() ||
      'Unnamed contact',
  },
  {
    id: 'position',
    header: 'Position',
    cell: (contact) => contact.position || 'Not specified',
  },
  { id: 'email', header: 'Email', cell: (contact) => contact.email },
  { id: 'phone', header: 'Phone', cell: (contact) => contact.phone || 'Not provided' },
  {
    id: 'created_at',
    header: 'Created',
    cell: (contact) => formatDate(contact.created_at),
  },
];

const dealColumns: readonly DataTableColumn<DealItem>[] = [
  { id: 'title', header: 'Deal', cell: (deal) => deal.title || 'Untitled deal' },
  { id: 'stage', header: 'Stage', cell: (deal) => deal.stage || 'Not specified' },
  {
    id: 'amount',
    header: 'Amount',
    cell: (deal) => formatInvoiceMoney(deal.amount),
  },
  {
    id: 'probability',
    header: 'Probability',
    cell: (deal) =>
      typeof deal.probability === 'number' ? `${deal.probability}%` : 'Not specified',
  },
  {
    id: 'expected_close_date',
    header: 'Expected Close',
    cell: (deal) => formatDate(deal.expected_close_date),
  },
];

const noteColumns: readonly DataTableColumn<NoteItem>[] = [
  { id: 'content', header: 'Note', cell: (note) => note.content || 'Empty note' },
  {
    id: 'created_by',
    header: 'Created By',
    cell: (note) => note.created_by || 'System user',
  },
  {
    id: 'created_at',
    header: 'Created',
    cell: (note) => formatDateTime(note.created_at),
  },
];

const quoteColumns: readonly DataTableColumn<QuoteItem>[] = [
  {
    id: 'quote_number',
    header: 'Quote',
    cell: (quote) => quote.quote_number || 'Unnumbered quote',
  },
  { id: 'status', header: 'Status', cell: (quote) => quote.status || 'Draft' },
  {
    id: 'total_amount',
    header: 'Total',
    cell: (quote) => formatInvoiceMoney(quote.total_amount, quote.currency ?? undefined),
  },
  {
    id: 'due_date',
    header: 'Valid Until',
    cell: (quote) => formatDate(quote.due_date ?? quote.expires_at),
  },
  {
    id: 'created_at',
    header: 'Created',
    cell: (quote) => formatDate(quote.created_at),
  },
];

const invoiceColumns: readonly DataTableColumn<InvoiceItem>[] = [
  {
    id: 'invoice_number',
    header: 'Invoice',
    cell: (invoice) => invoice.invoice_number || 'Unnumbered invoice',
  },
  { id: 'status', header: 'Invoice Status', cell: (invoice) => invoice.status },
  {
    id: 'payment_status',
    header: 'Payment Status',
    cell: (invoice) => invoice.payment_status || 'Pending',
  },
  {
    id: 'amount',
    header: 'Total',
    cell: (invoice) => formatInvoiceMoney(invoice.amount, invoice.currency),
  },
  {
    id: 'outstanding_amount',
    header: 'Outstanding',
    cell: (invoice) =>
      formatInvoiceMoney(invoice.outstanding_amount ?? invoice.amount, invoice.currency),
  },
  {
    id: 'due_date',
    header: 'Due Date',
    cell: (invoice) => formatDate(invoice.due_date),
  },
];

function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return 'Not available';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const documentColumns: readonly DataTableColumn<DocumentItem>[] = [
  { id: 'filename', header: 'File', cell: (document) => document.filename },
  { id: 'mime_type', header: 'Type', cell: (document) => document.mime_type },
  {
    id: 'file_size',
    header: 'Size',
    cell: (document) => formatFileSize(document.file_size),
  },
  {
    id: 'uploaded_at',
    header: 'Uploaded',
    cell: (document) => formatDateTime(document.uploaded_at),
  },
  {
    id: 'download',
    header: 'Download',
    cell: (document) => (
      <a
        href={document.download_url}
        target="_blank"
        rel="noreferrer"
        className="font-semibold text-blue-600 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        onClick={(event: MouseEvent<HTMLAnchorElement>) => event.stopPropagation()}
      >
        Download
      </a>
    ),
  },
];

export function CompanyContactsTable({
  data,
  isLoading,
  onRowClick,
  pagination,
}: RelationshipTableProps<CompanyContactItem>) {
  return (
    <DataTable
      columns={contactColumns}
      data={data}
      getRowKey={(contact) => contact.id}
      emptyTitle="No associated contacts"
      emptyDescription="No contacts are associated with this company profile yet."
      isLoading={isLoading}
      onRowClick={onRowClick}
      pagination={pagination}
    />
  );
}

export function CompanyDealsTable({ data, isLoading, onRowClick, pagination }: RelationshipTableProps<DealItem>) {
  return (
    <DataTable
      columns={dealColumns}
      data={data}
      getRowKey={(deal) => deal.id}
      emptyTitle="No linked deals"
      emptyDescription="No sales pipeline deals are linked to this company profile yet."
      isLoading={isLoading}
      onRowClick={onRowClick}
      pagination={pagination}
    />
  );
}

export function CompanyNotesTable({ data, isLoading, pagination }: RelationshipTableProps<NoteItem>) {
  return (
    <DataTable
      columns={noteColumns}
      data={data}
      getRowKey={(note) => note.id}
      emptyTitle="No company notes"
      emptyDescription="No notes have been logged for this company yet."
      isLoading={isLoading}
      pagination={pagination}
    />
  );
}

export function CompanyQuotesTable({
  data,
  isLoading,
  onRowClick,
  pagination,
}: RelationshipTableProps<QuoteItem>) {
  return (
    <DataTable
      columns={quoteColumns}
      data={data}
      getRowKey={(quote) => quote.id}
      emptyTitle="No generated quotes"
      emptyDescription="No quotes have been generated for this company yet."
      isLoading={isLoading}
      onRowClick={onRowClick}
      pagination={pagination}
    />
  );
}

export function CompanyInvoicesTable({
  data,
  isLoading,
  onRowClick,
  pagination,
}: RelationshipTableProps<InvoiceItem>) {
  return (
    <DataTable
      columns={invoiceColumns}
      data={data}
      getRowKey={(invoice) => invoice.id}
      emptyTitle="No billed invoices"
      emptyDescription="No invoices have been generated for this company yet."
      isLoading={isLoading}
      onRowClick={onRowClick}
      pagination={pagination}
    />
  );
}

export function CompanyDocumentsTable({ data, isLoading }: RelationshipTableProps<DocumentItem>) {
  return (
    <DataTable
      columns={documentColumns}
      data={data}
      getRowKey={(document) => document.id}
      emptyTitle="No attached documents"
      emptyDescription="No files or contract documents are attached to this company."
      isLoading={isLoading}
      pagination={{ pageSize: 15 }}
    />
  );
}

export function CompanyRelationshipError({
  resourceName,
  onRetry,
  unavailable = false,
}: RelationshipErrorProps) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs font-medium text-amber-900 sm:flex-row sm:items-center sm:justify-between"
    >
      <span>
        {unavailable
          ? `${resourceName} are not linked to companies yet.`
          : `${resourceName} could not be loaded. Try again.`}
      </span>
      {!unavailable && (
        <Button type="button" size="sm" variant="outline" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
