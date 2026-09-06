import { z } from 'zod';
import { manualPaymentSchema } from '@/lib/types/manual-payment';

const pendingPaymentSchema = z.object({ idempotencyKey: z.string().uuid(), payment: manualPaymentSchema });
export type PendingPayment = z.infer<typeof pendingPaymentSchema>;
export const pendingPaymentKey = (userId: string, invoiceId: string) => `pending-invoice-payment:${userId}:${invoiceId}`;

export function readPendingPayment(key: string): PendingPayment | null {
  const raw = sessionStorage.getItem(key);
  return raw ? pendingPaymentSchema.parse(JSON.parse(raw)) : null;
}

export function savePendingPayment(key: string, operation: PendingPayment) {
  sessionStorage.setItem(key, JSON.stringify(operation));
}
