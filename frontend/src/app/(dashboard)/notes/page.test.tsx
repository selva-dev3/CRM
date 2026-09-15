import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  notesQuery: vi.fn(),
  pinnedNotesQuery: vi.fn(),
}));

vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({ hasPermission: () => true }),
}));

vi.mock('@/components/common/permission-gate', () => ({
  PermissionGate: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/lib/api/notes', () => ({
  useNotesQuery: (...args: unknown[]) => mocks.notesQuery(...args),
  usePinnedNotesQuery: (...args: unknown[]) => mocks.pinnedNotesQuery(...args),
  useCreateNoteMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateNoteMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteNoteMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useBulkDeleteNotesMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  usePinNoteMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUnpinNoteMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import NotesPage from './page';

describe('NotesPage entity presentation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pinnedNotesQuery.mockReturnValue({ data: [] });
    mocks.notesQuery.mockReturnValue({
      data: {
        items: [
          {
            id: 'note-company',
            entity_type: 'company',
            entity_id: 'company-uuid-must-not-be-visible',
            entity_label: 'Acme Corporation',
            content: 'Discuss renewal terms',
            created_by: 'user-uuid-must-not-be-visible',
            created_by_name: 'Ada Lovelace',
            created_at: '2026-09-15T08:30:00Z',
          },
          {
            id: 'note-contact',
            entity_type: 'Contact',
            entity_id: 'contact-uuid-must-not-be-visible',
            entity_label: 'Grace Hopper',
            content: 'Requested a demonstration',
            created_by: null,
            created_by_name: null,
            created_at: '2026-09-15T08:00:00Z',
          },
        ],
        total: 2,
      },
      isLoading: false,
    });
  });

  it('shows linked record and author names while keeping UUIDs out of visible text', () => {
    render(<NotesPage />);

    expect(screen.getByRole('link', { name: 'Acme Corporation' })).toHaveAttribute(
      'href',
      '/companies/company-uuid-must-not-be-visible',
    );
    expect(screen.getByRole('link', { name: 'Grace Hopper' })).toHaveAttribute(
      'href',
      '/contacts/contact-uuid-must-not-be-visible',
    );
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    expect(screen.getByText('System / former user')).toBeInTheDocument();
    expect(screen.queryByText(/uuid-must-not-be-visible/)).not.toBeInTheDocument();
  });

  it('does not turn an unavailable relationship into an ID link', () => {
    mocks.notesQuery.mockReturnValue({
      data: {
        items: [{
          id: 'note-deleted',
          entity_type: 'company',
          entity_id: 'deleted-company-id',
          entity_label: null,
          content: 'Historical note',
          created_by: null,
          created_by_name: null,
          created_at: '2026-09-15T08:30:00Z',
        }],
        total: 1,
      },
      isLoading: false,
    });

    render(<NotesPage />);

    expect(screen.getByText('Unavailable company')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Unavailable company' })).not.toBeInTheDocument();
    expect(screen.queryByText('deleted-company-id')).not.toBeInTheDocument();
  });
});
