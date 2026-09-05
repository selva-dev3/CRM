import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  DatePicker,
  DateTimePicker,
  formatDateTimeValue,
  getTimeValue,
  parseLocalDate,
  toDateValue,
} from './date-picker';

describe('date picker value handling', () => {
  it('round-trips date-only values without a UTC conversion', () => {
    const date = parseLocalDate('2026-09-05');

    expect(date).toBeDefined();
    expect(toDateValue(date!)).toBe('2026-09-05');
  });

  it('rejects invalid date-only values', () => {
    expect(parseLocalDate('2026-02-30')).toBeUndefined();
    expect(parseLocalDate('not-a-date')).toBeUndefined();
  });

  it('preserves and formats the local time portion', () => {
    expect(getTimeValue('2026-09-05T13:45')).toBe('13:45');
    expect(formatDateTimeValue('2026-09-05T13:45')).toContain('1:45 PM');
  });

  it('clears a selected date', () => {
    const onValueChange = vi.fn();
    render(
      <DatePicker
        aria-label="Due date"
        value="2026-09-05"
        onValueChange={onValueChange}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Due date' }));
    fireEvent.click(screen.getByRole('button', { name: 'Clear date' }));

    expect(onValueChange).toHaveBeenCalledWith('');
  });

  it('applies a changed time without changing the selected date', () => {
    const onValueChange = vi.fn();
    render(
      <DateTimePicker
        aria-label="Meeting time"
        value="2026-09-05T13:30"
        onValueChange={onValueChange}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Meeting time' }));
    fireEvent.change(screen.getByLabelText('Time'), { target: { value: '14:45' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(onValueChange).toHaveBeenCalledWith('2026-09-05T14:45');
  });
});
