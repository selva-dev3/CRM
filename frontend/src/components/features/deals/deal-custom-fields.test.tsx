import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { DealCustomFields } from './deal-custom-fields';

describe('DealCustomFields', () => {
  it('renders API field definitions and reports entered values', async () => {
    const onChange = vi.fn();
    render(
      <DealCustomFields
        fields={[
          { field_name: 'decision_maker', field_type: 'text', label: 'Decision Maker', options: [] },
          { field_name: 'priority', field_type: 'select', label: 'Priority', options: ['High', 'Low'] },
          { field_name: 'renewal', field_type: 'boolean', label: 'Renewal', options: [] },
        ]}
        values={{}}
        onChange={onChange}
        isLoading={false}
        isError={false}
      />,
    );

    fireEvent.change(screen.getByLabelText('Decision Maker'), { target: { value: 'CTO' } });
    fireEvent.keyDown(screen.getByLabelText('Priority'), { key: 'ArrowDown' });
    fireEvent.click(await screen.findByRole('option', { name: 'High' }));
    fireEvent.keyDown(screen.getByLabelText('Renewal'), { key: 'ArrowDown' });
    fireEvent.click(await screen.findByRole('option', { name: 'Yes' }));

    expect(onChange).toHaveBeenCalledWith('decision_maker', 'CTO');
    expect(onChange).toHaveBeenCalledWith('priority', 'High');
    expect(onChange).toHaveBeenCalledWith('renewal', true);
  });

  it('supports explicit false and unset boolean values', async () => {
    const onChange = vi.fn();
    render(
      <DealCustomFields
        fields={[
          { field_name: 'renewal', field_type: 'boolean', label: 'Renewal', options: [] },
        ]}
        values={{ renewal: false }}
        onChange={onChange}
        isLoading={false}
        isError={false}
      />,
    );

    fireEvent.keyDown(screen.getByLabelText('Renewal'), { key: 'ArrowDown' });
    fireEvent.click(await screen.findByRole('option', { name: '-- Not set --' }));

    expect(onChange).toHaveBeenCalledWith('renewal', null);
  });

  it('reports null when a selected option is cleared', async () => {
    const onChange = vi.fn();
    render(
      <DealCustomFields
        fields={[
          { field_name: 'priority', field_type: 'select', label: 'Priority', options: ['High'] },
        ]}
        values={{ priority: 'High' }}
        onChange={onChange}
        isLoading={false}
        isError={false}
      />,
    );

    fireEvent.keyDown(screen.getByLabelText('Priority'), { key: 'ArrowDown' });
    fireEvent.click(await screen.findByRole('option', { name: '-- Select --' }));

    expect(onChange).toHaveBeenCalledWith('priority', null);
  });

  it('preserves an option that matches the default empty-value marker', async () => {
    const onChange = vi.fn();
    render(
      <DealCustomFields
        fields={[
          {
            field_name: 'segment',
            field_type: 'select',
            label: 'Segment',
            options: ['__deal_custom_field_empty__'],
          },
        ]}
        values={{}}
        onChange={onChange}
        isLoading={false}
        isError={false}
      />,
    );

    fireEvent.keyDown(screen.getByLabelText('Segment'), { key: 'ArrowDown' });
    fireEvent.click(await screen.findByRole('option', { name: '__deal_custom_field_empty__' }));

    expect(onChange).toHaveBeenCalledWith('segment', '__deal_custom_field_empty__');
  });

  it('does not render fabricated fields for an empty response', () => {
    const { container } = render(
      <DealCustomFields
        fields={[]}
        values={{}}
        onChange={vi.fn()}
        isLoading={false}
        isError={false}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
