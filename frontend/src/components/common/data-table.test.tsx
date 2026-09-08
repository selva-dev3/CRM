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

  it('executes a row action without opening the row', async () => {
    const user = userEvent.setup();
    const onRowClick = vi.fn();
    const onEdit = vi.fn();
    const row = { id: 'lead-1', name: 'Jane Doe' };

    render(
      <DataTable
        columns={columns}
        data={[row]}
        getRowKey={(item) => item.id}
        emptyTitle="No rows"
        emptyDescription="No rows found"
        onRowClick={onRowClick}
        actionVariant="menu"
        actions={[{ label: 'Edit', onClick: onEdit }]}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Open row actions' }));
    await user.click(screen.getByRole('menuitem', { name: 'Edit' }));

    expect(onEdit).toHaveBeenCalledWith(row);
    expect(onRowClick).not.toHaveBeenCalled();
  });

  it('preserves compact table widths and disabled inline actions', async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();

    render(
      <DataTable
        columns={columns}
        data={[{ id: 'lead-1', name: 'Jane Doe' }]}
        getRowKey={(item) => item.id}
        emptyTitle="No rows"
        emptyDescription="No rows found"
        tableClassName="min-w-[560px]"
        actionVariant="inline"
        actions={[{
          id: 'open',
          label: 'Opening…',
          ariaLabel: 'Open Jane Doe',
          disabled: true,
          isLoading: true,
          onClick: onOpen,
        }]}
      />,
    );

    expect(screen.getByRole('table')).toHaveClass('min-w-[560px]');
    expect(screen.getByRole('columnheader', { name: 'Actions' })).toBeInTheDocument();
    const action = screen.getByRole('button', { name: 'Open Jane Doe' });
    expect(action).toBeDisabled();
    expect(action).toHaveAttribute('aria-busy', 'true');
    await user.click(action);
    expect(onOpen).not.toHaveBeenCalled();
  });

  it('preserves inline action focus when its loading label changes', () => {
    const row = { id: 'lead-1', name: 'Jane Doe' };
    const { rerender } = render(
      <DataTable
        columns={columns}
        data={[row]}
        getRowKey={(item) => item.id}
        emptyTitle="No rows"
        emptyDescription="No rows found"
        actionVariant="inline"
        actions={[{ id: 'open', label: 'Open', ariaLabel: 'Open Jane Doe', onClick: vi.fn() }]}
      />,
    );

    screen.getByRole('button', { name: 'Open Jane Doe' }).focus();
    rerender(
      <DataTable
        columns={columns}
        data={[row]}
        getRowKey={(item) => item.id}
        emptyTitle="No rows"
        emptyDescription="No rows found"
        actionVariant="inline"
        actions={[{ id: 'open', label: 'Opening…', ariaLabel: 'Open Jane Doe', isLoading: true, onClick: vi.fn() }]}
      />,
    );

    expect(screen.getByRole('button', { name: 'Open Jane Doe' })).toHaveFocus();
  });

  it('announces loading state and hides decorative skeleton rows', () => {
    render(
      <DataTable
        columns={columns}
        data={[]}
        getRowKey={(item) => item.id}
        emptyTitle="No rows"
        emptyDescription="No rows found"
        isLoading
        loadingLabel="Loading leads"
      />,
    );

    expect(screen.getByRole('status')).toHaveTextContent('Loading leads');
    expect(screen.getByRole('status').parentElement).toHaveAttribute('aria-busy', 'true');
    expect(document.querySelector('tbody')).toHaveAttribute('aria-hidden', 'true');
  });

  it('returns to the last available page when uncontrolled data shrinks', async () => {
    const user = userEvent.setup();
    const rows = Array.from({ length: 16 }, (_, index) => ({
      id: `lead-${index + 1}`,
      name: `Lead ${index + 1}`,
    }));

    const { rerender } = render(
      <DataTable
        columns={columns}
        data={rows}
        getRowKey={(item) => item.id}
        emptyTitle="No rows"
        emptyDescription="No rows found"
        pagination={{ pageSize: 15 }}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByText('Lead 16')).toBeInTheDocument();

    rerender(
      <DataTable
        columns={columns}
        data={rows.slice(0, 15)}
        getRowKey={(item) => item.id}
        emptyTitle="No rows"
        emptyDescription="No rows found"
        pagination={{ pageSize: 15 }}
      />,
    );

    expect(screen.getByText('Lead 1')).toBeInTheDocument();
    expect(screen.queryByText('No rows')).not.toBeInTheDocument();
  });
});
