export function formatInvoiceMoney(value: number | string | null | undefined, currency?: string): string {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  if (!currency) return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2 });
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value));
}
