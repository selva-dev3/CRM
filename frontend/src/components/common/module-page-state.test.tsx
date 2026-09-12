import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { PageNavigator } from './module-page-state';

describe('PageNavigator', () => {
  it('clamps the page when deletion reduces the total page count', async () => {
    const onChange = vi.fn();

    render(<PageNavigator page={2} total={20} limit={20} onChange={onChange} />);

    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled();
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(1));
  });

  it('does not render navigation for a single current page', () => {
    render(<PageNavigator page={1} total={20} limit={20} onChange={vi.fn()} />);

    expect(screen.queryByRole('navigation', { name: 'Pagination' })).not.toBeInTheDocument();
  });
});
