import type { InvoiceItem, InvoiceLineItem } from '@/lib/api/invoices';

export type DecimalDto = number | string;
export type PublicInvoiceDto = {
  invoice_number: string;
  status: 'Draft' | 'Finalized' | 'Accepted' | 'Cancelled';
  currency: string;
  amount: DecimalDto;
  subtotal: DecimalDto;
  discount_total: DecimalDto;
  tax_total: DecimalDto;
  due_date?: string | null;
  items: (Omit<InvoiceLineItem, 'unit_price' | 'total' | 'subtotal' | 'discount_total' | 'tax_total'> & {
    unit_price: DecimalDto; total?: DecimalDto; subtotal?: DecimalDto; discount_total?: DecimalDto; tax_total?: DecimalDto;
  })[];
  billing_snapshot: InvoiceItem['billing_snapshot'];
  pdf_url?: string | null;
  accepted_at?: string | null;
  created_at?: string | null;
  payment_status: 'Pending' | 'Partially Paid' | 'Paid';
};
