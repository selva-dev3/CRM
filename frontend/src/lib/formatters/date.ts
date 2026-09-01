export type DateValue = Date | string | number | null | undefined;

interface DateFormatOptions {
  readonly fallback?: string;
  readonly locale?: string | readonly string[];
  readonly timeZone?: string;
}

function parseDate(value: DateValue): Date | null {
  if (value === null || value === undefined || value === '') return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;

  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split('-').map(Number);
    const localDate = new Date(year, month - 1, day);
    if (
      Number.isNaN(localDate.getTime()) ||
      localDate.getFullYear() !== year ||
      localDate.getMonth() !== month - 1 ||
      localDate.getDate() !== day
    ) {
      return null;
    }
    return localDate;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function normalizeTimeZone(timeZone: string | undefined): string | undefined {
  if (!timeZone) return undefined;
  try {
    new Intl.DateTimeFormat('en-US', { timeZone }).format();
    return timeZone;
  } catch {
    return 'UTC';
  }
}

export function formatDate(
  value: DateValue,
  { fallback = 'N/A', locale, timeZone }: DateFormatOptions = {},
): string {
  const date = parseDate(value);
  if (!date) return fallback;

  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: normalizeTimeZone(timeZone),
  }).format(date);
}

export function formatDateTime(
  value: DateValue,
  { fallback = 'N/A', locale, timeZone }: DateFormatOptions = {},
): string {
  const date = parseDate(value);
  if (!date) return fallback;

  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: normalizeTimeZone(timeZone),
  }).format(date);
}
