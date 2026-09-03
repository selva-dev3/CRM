import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GlobalSearchModal } from './global-search-modal';

const routerPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: routerPush }),
}));

describe('GlobalSearchModal', () => {
  beforeEach(() => {
    routerPush.mockReset();
  });

  it('selects the highlighted result with Enter after keyboard navigation', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<GlobalSearchModal isOpen onClose={onClose} />);

    await user.keyboard('{ArrowDown}{Enter}');

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(routerPush).toHaveBeenCalledWith('/leads');
  });

  it('wraps keyboard navigation at both ends of the result list', async () => {
    const user = userEvent.setup();
    render(<GlobalSearchModal isOpen onClose={vi.fn()} />);

    await user.keyboard('{ArrowUp}');
    expect(screen.getByText('System Settings').closest('[class*="bg-blue-50"]')).toBeInTheDocument();

    await user.keyboard('{ArrowDown}');
    expect(screen.getByText('Dashboard').closest('[class*="bg-blue-50"]')).toBeInTheDocument();
  });

  it('resets selection when the query changes and closes with Escape', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<GlobalSearchModal isOpen onClose={onClose} />);
    const input = screen.getByPlaceholderText('Search CRM pages, modules, settings...');

    await user.keyboard('{ArrowDown}');
    await user.type(input, 'invoice');
    expect(screen.getByText('Invoices').closest('[class*="bg-blue-50"]')).toBeInTheDocument();

    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
