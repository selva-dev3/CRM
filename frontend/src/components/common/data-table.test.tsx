import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { DataTable, type DataTableColumn } from './data-table';

interface RowItem {
  id: string;
  name: string;
}

const columns: DataTableColumn<RowItem>[] = [
  {
    id: 'name',
    header: 'Name',
    cell: (item) => item.name,
  },
];

describe('DataTable selection', () => {
  it('exposes and highlights selected rows with descriptive controls', () => {
    render(
      <DataTable
        columns={columns}
        data={[{ id: 'lead-1', name: 'Jane Doe' }]}
        getRowKey={(item) => item.id}
        emptyTitle="No rows"
        emptyDescription="No rows found"
        showCheckbox
        selectedIds={new Set(['lead-1'])}
        getSelectionLabel={(item) => `Select ${item.name}`}
      />,
    );

    const checkbox = screen.getByRole('checkbox', { name: 'Select Jane Doe' });
    const row = screen.getByText('Jane Doe').closest('tr');

    expect(checkbox).toBeChecked();
    expect(checkbox.parentElement).toHaveClass('size-11');
    expect(row).toHaveAttribute('aria-selected', 'true');
    expect(row).toHaveClass('bg-blue-50/80');
  });

  it('keeps hidden columns out of the loading skeleton', async () => {
    const user = userEvent.setup();
    const hideableColumns: DataTableColumn<RowItem>[] = [
      columns[0],
      {
        id: 'email',
        header: 'Email',
        cell: () => 'jane@example.com',
        enableHiding: true,
      },
    ];

    const { rerender } = render(
      <DataTable
        columns={hideableColumns}
        data={[{ id: 'lead-1', name: 'Jane Doe' }]}
        getRowKey={(item) => item.id}
        emptyTitle="No rows"
        emptyDescription="No rows found"
        searchValue=""
        onSearchChange={vi.fn()}
      />,
    );

    expect(screen.getByRole('columnheader', { name: 'Email' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.click(screen.getByRole('menuitemcheckbox', { name: 'Email' }));

    rerender(
      <DataTable
        columns={hideableColumns}
        data={[]}
        getRowKey={(item) => item.id}
        emptyTitle="No rows"
        emptyDescription="No rows found"
        searchValue=""
        onSearchChange={vi.fn()}
        isLoading
      />,
    );

    expect(screen.queryByRole('columnheader', { name: 'Email' })).not.toBeInTheDocument();
  });

  it('toggles selection without opening the row', async () => {
    const user = userEvent.setup();
    const onToggleRow = vi.fn();
    const onRowClick = vi.fn();

    render(
      <DataTable
        columns={columns}
        data={[{ id: 'lead-1', name: 'Jane Doe' }]}
        getRowKey={(item) => item.id}
        emptyTitle="No rows"
        emptyDescription="No rows found"
        showCheckbox
        selectedIds={new Set()}
        onToggleRow={onToggleRow}
        onRowClick={onRowClick}
        getSelectionLabel={(item) => `Select ${item.name}`}
      />,
    );

    await user.click(screen.getByRole('checkbox', { name: 'Select Jane Doe' }));

    expect(onToggleRow).toHaveBeenCalledWith({ id: 'lead-1', name: 'Jane Doe' }, true);
    expect(onRowClick).not.toHaveBeenCalled();
  });
});
