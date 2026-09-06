import { z } from 'zod';

export const paymentTypes = ['Cash', 'Bank Transfer', 'Cheque', 'UPI', 'Card', 'Other'] as const;

export const manualPaymentSchema = z.object({
  payment_type: z.enum(paymentTypes),
  amount: z.string().trim().regex(/^\d+(\.\d{1,2})?$/, 'Enter an amount with at most two decimal places.').refine((value) => Number.isFinite(Number(value)) && Number(value) > 0, 'Amount must be greater than zero.').refine((value) => Number(value) <= 999999999999.99, 'Amount must not exceed 999999999999.99.'),
  payment_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid date.').refine((value) => {
    const date = new Date(`${value}T00:00:00Z`);
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }, 'Enter a valid date.').refine((value) => value <= new Date().toISOString().slice(0, 10), 'Payment date must not be in the future (UTC).'),
  notes: z.string().trim().max(2000, 'Notes must not exceed 2000 characters.').optional(),
});

export type ManualPaymentDto = z.infer<typeof manualPaymentSchema>;
