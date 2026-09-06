import { render, screen } from '@testing-library/react';
import { it, expect } from 'vitest';
import Page from './page';

it('shows cancellation without claiming payment or subscription status', () => {
  render(<Page />);
  expect(screen.getByRole('heading')).toHaveTextContent('Subscription checkout cancelled');
  expect(screen.getByText(/does not verify payment or subscription status/)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'View subscription plans' })).toHaveAttribute('href', '/organization/subscription/plans');
});
