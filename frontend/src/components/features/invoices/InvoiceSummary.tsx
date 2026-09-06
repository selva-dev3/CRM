import type { InvoiceItem } from '@/lib/api/invoices';
import type { DecimalDto } from '@/lib/types/public-invoice';
import { formatDateTime } from '@/lib/formatters/date';
import { formatInvoiceMoney } from '@/lib/formatters/invoice';

type Summary = Pick<InvoiceItem, 'currency' | 'billing_snapshot' | 'accepted_at' | 'finalized_at' | 'paid_amount' | 'outstanding_amount'> & {
  amount: DecimalDto; subtotal?: DecimalDto; discount_total?: DecimalDto; tax_total?: DecimalDto;
};

function SnapshotValue({ value }: { value: unknown }) {
  if (value == null) return <span>—</span>;
  if (typeof value === 'object') return <dl className="space-y-1 pl-3">{Object.entries(value).map(([key, item]) => <div key={key}><dt className="text-muted-foreground">{key.replaceAll('_', ' ')}</dt><dd className="break-words"><SnapshotValue value={item} /></dd></div>)}</dl>;
  return <span>{String(value)}</span>;
}

export function InvoiceSummary({ invoice }: { invoice: Summary }) {
  return <section className="space-y-4">
    <h2 className="font-semibold">Invoice totals</h2>
    <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">{([
      ['Subtotal', invoice.subtotal], ['Discount', invoice.discount_total], ['Tax', invoice.tax_total], ['Total', invoice.amount], ['Paid', invoice.paid_amount], ['Outstanding', invoice.outstanding_amount],
    ] as const).filter(([, value]) => value !== undefined).map(([label, value]) => <div key={label}><dt className="text-sm text-muted-foreground">{label}</dt><dd>{formatInvoiceMoney(value, invoice.currency)}</dd></div>)}</dl>
    {invoice.finalized_at && <p>Finalized: {formatDateTime(invoice.finalized_at)}</p>}
    {invoice.accepted_at && <p>Accepted: {formatDateTime(invoice.accepted_at)}</p>}
    <h2 className="font-semibold">Billing details</h2>
    {invoice.billing_snapshot ? <SnapshotValue value={invoice.billing_snapshot} /> : <p className="text-sm text-muted-foreground">Billing snapshot is not available.</p>}
  </section>;
}
