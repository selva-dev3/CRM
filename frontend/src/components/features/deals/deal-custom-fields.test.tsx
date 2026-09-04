import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { DealCustomFields } from './deal-custom-fields';

describe('DealCustomFields', () => {
  it('renders API field definitions and reports entered values', () => {
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
    fireEvent.change(screen.getByLabelText('Priority'), { target: { value: 'High' } });
    fireEvent.click(screen.getByLabelText('Renewal'));

    expect(onChange).toHaveBeenCalledWith('decision_maker', 'CTO');
    expect(onChange).toHaveBeenCalledWith('priority', 'High');
    expect(onChange).toHaveBeenCalledWith('renewal', true);
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
