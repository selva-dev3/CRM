import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ModalShell } from './modal-shell';

describe('ModalShell', () => {
  it('renders a visible close button when the modal has no title', () => {
    render(
      <ModalShell isOpen onClose={vi.fn()}>
        <p>Body without title</p>
      </ModalShell>,
    );
    expect(screen.getByRole('button', { name: 'Close dialog' })).toBeInTheDocument();
  });

  it('renders the close button when a title is present', () => {
    render(
      <ModalShell isOpen onClose={vi.fn()} title="Edit Deal">
        <p>Body</p>
      </ModalShell>,
    );
    expect(screen.getByRole('button', { name: 'Close dialog' })).toBeInTheDocument();
    expect(screen.getAllByText('Edit Deal')).toHaveLength(2);
  });

  it('gives title-less dialogs a generic accessible name', () => {
    render(
      <ModalShell isOpen onClose={vi.fn()}>
        <p>Body</p>
      </ModalShell>,
    );
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Dialog');
  });

  it('prefers an explicit ariaLabel as the accessible name', () => {
    render(
      <ModalShell isOpen onClose={vi.fn()} ariaLabel="Delete confirmation">
        <p>Body</p>
      </ModalShell>,
    );
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Delete confirmation');
  });

  it('moves focus into the dialog on open and restores it on close', async () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <>
        <button type="button">Trigger</button>
        <ModalShell isOpen={false} onClose={onClose}>
          <input aria-label="Field" />
        </ModalShell>
      </>,
    );
    const trigger = screen.getByRole('button', { name: 'Trigger' });
    trigger.focus();
    rerender(
      <>
        <button type="button">Trigger</button>
        <ModalShell isOpen onClose={onClose}>
          <input aria-label="Field" />
        </ModalShell>
      </>,
    );

    // Radix moves focus to the first interactive control.
    await vi.waitFor(() => {
      expect(document.activeElement).toBe(
        screen.getByRole('button', { name: 'Close dialog' }),
      );
    });

    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);

    rerender(
      <>
        <button type="button">Trigger</button>
        <ModalShell isOpen={false} onClose={onClose}>
          <input aria-label="Field" />
        </ModalShell>
      </>,
    );
    // Focus returns to the element that opened the dialog.
    await vi.waitFor(() => {
      expect(document.activeElement).toBe(trigger);
    });
  });

  it('keeps Tab cycling inside the panel (focus trap)', async () => {
    render(
      <ModalShell isOpen onClose={vi.fn()}>
        <button type="button">First</button>
        <button type="button">Last</button>
      </ModalShell>,
    );
    const closeButton = screen.getByRole('button', { name: 'Close dialog' });
    const first = screen.getByRole('button', { name: 'First' });
    const last = screen.getByRole('button', { name: 'Last' });

    await vi.waitFor(() => {
      expect(document.activeElement).toBe(closeButton);
    });

    await userEvent.tab();
    expect(document.activeElement).toBe(first);
    await userEvent.tab();
    expect(document.activeElement).toBe(last);
    await userEvent.tab();
    expect(document.activeElement).toBe(closeButton);

    await userEvent.tab({ shift: true });
    expect(document.activeElement).toBe(last);
  });

  it('clicking the close button invokes onClose', async () => {
    const onClose = vi.fn();
    render(
      <ModalShell isOpen onClose={onClose} ariaLabel="Confirm">
        <p>Body</p>
      </ModalShell>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Close dialog' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders nothing when closed', () => {
    render(
      <ModalShell isOpen={false} onClose={vi.fn()}>
        <p>Hidden</p>
      </ModalShell>,
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
