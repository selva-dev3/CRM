import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { PublicInvoiceDto } from '@/lib/types/public-invoice';
import { formatInvoiceMoney } from '@/lib/formatters/invoice';

export function InvoiceItemsTable({ items, currency }: { items?: PublicInvoiceDto['items']; currency?: string }) {
  return <div className="overflow-x-auto"><Table className="min-w-[640px]">
    <TableHeader><TableRow><TableHead>Product / Description</TableHead><TableHead>Quantity</TableHead><TableHead>Unit price</TableHead><TableHead>Discount %</TableHead><TableHead>Tax %</TableHead><TableHead>Total</TableHead></TableRow></TableHeader>
    <TableBody>{items?.length ? items.map((item, index) => <TableRow key={item.id || index}>
      <TableCell><p>{item.product_name || item.description || item.product_id}</p>{item.product_name && item.description && <p className="text-sm text-muted-foreground">{item.description}</p>}</TableCell>
      <TableCell>{item.quantity}</TableCell><TableCell>{formatInvoiceMoney(item.unit_price, currency)}</TableCell><TableCell>{item.discount_percent ?? '—'}</TableCell><TableCell>{item.tax_percent ?? '—'}</TableCell><TableCell>{formatInvoiceMoney(item.total, currency)}</TableCell>
    </TableRow>) : <TableRow><TableCell colSpan={6}>No line items available.</TableCell></TableRow>}</TableBody>
  </Table></div>;
}
