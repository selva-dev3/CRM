import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import {
  EMPTY_SELECT_VALUE,
  ResponsiveSelect,
  toExternalValue,
  toInternalValue,
} from './responsive-select';

describe('ResponsiveSelect value translation', () => {
  it('maps an empty form value to a non-empty Radix value', () => {
    expect(toInternalValue('')).toBe(EMPTY_SELECT_VALUE);
  });

  it('maps the internal empty option back to the API form value', () => {
    expect(toExternalValue(EMPTY_SELECT_VALUE)).toBe('');
  });

  it('preserves real option values', () => {
    expect(toInternalValue('Closed Won')).toBe('Closed Won');
    expect(toExternalValue('Closed Won')).toBe('Closed Won');
  });

  it('preserves an uncontrolled value', () => {
    expect(toInternalValue(undefined)).toBeUndefined();
  });

  it('renders options in a portaled listbox and returns the selected value', async () => {
    const onValueChange = vi.fn();
    const user = userEvent.setup();

    render(
      <ResponsiveSelect
        aria-label="Pipeline stage"
        value="Prospecting"
        onValueChange={onValueChange}
      >
        <option value="Prospecting">Prospecting</option>
        <option value="Qualification">Qualification</option>
      </ResponsiveSelect>,
    );

    screen.getByRole('combobox', { name: 'Pipeline stage' }).focus();
    await user.keyboard('{Enter}');
    expect(screen.getByRole('option', { name: 'Qualification' })).toBeInTheDocument();
    await user.keyboard('{ArrowDown}{Enter}');

    expect(onValueChange).toHaveBeenCalledWith('Qualification');
  });
});
