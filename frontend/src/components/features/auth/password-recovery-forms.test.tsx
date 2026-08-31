import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ForgotPasswordForm } from './forgot-password-form';
import { ResetPasswordForm } from './reset-password-form';

const mocks = vi.hoisted(() => ({
  forgotMutateAsync: vi.fn(),
  resetMutateAsync: vi.fn(),
  searchToken: 'ABCDEFGHIJKLMN',
  useForgotPasswordMutation: vi.fn(),
  useResetPasswordMutation: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => ({ get: () => mocks.searchToken }),
}));

vi.mock('@/lib/api', () => ({
  useForgotPasswordMutation: () => mocks.useForgotPasswordMutation(),
  useResetPasswordMutation: () => mocks.useResetPasswordMutation(),
}));

describe('password recovery forms', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.searchToken = 'ABCDEFGHIJKLMN';
    mocks.useForgotPasswordMutation.mockReturnValue({
      isPending: false,
      mutateAsync: mocks.forgotMutateAsync,
    });
    mocks.useResetPasswordMutation.mockReturnValue({
      isPending: false,
      mutateAsync: mocks.resetMutateAsync,
    });
  });

  it('validates email before requesting a reset link', async () => {
    const user = userEvent.setup();
    render(<ForgotPasswordForm />);

    await user.click(screen.getByRole('button', { name: 'Send reset link' }));

    expect(await screen.findByText('Work email is required')).toBeInTheDocument();
    expect(mocks.forgotMutateAsync).not.toHaveBeenCalled();
  });

  it('shows an account-safe confirmation after requesting a reset link', async () => {
    const user = userEvent.setup();
    mocks.forgotMutateAsync.mockResolvedValue({ message: 'sent', status: 'success' });
    render(<ForgotPasswordForm />);

    await user.type(screen.getByLabelText('Work email'), 'alex@crm.com');
    await user.click(screen.getByRole('button', { name: 'Send reset link' }));

    expect(
      await screen.findByText(/If an account exists for that address/i),
    ).toBeInTheDocument();
    expect(mocks.forgotMutateAsync).toHaveBeenCalledWith({ email: 'alex@crm.com' });
  });

  it('blocks mismatched passwords', async () => {
    const user = userEvent.setup();
    render(<ResetPasswordForm />);

    await user.type(screen.getByLabelText('New password'), 'new-password');
    await user.type(screen.getByLabelText('Confirm password'), 'different-password');
    await user.click(screen.getByRole('button', { name: 'Update password' }));

    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument();
    expect(mocks.resetMutateAsync).not.toHaveBeenCalled();
  });

  it('submits the reset token and new password then shows success', async () => {
    const user = userEvent.setup();
    mocks.resetMutateAsync.mockResolvedValue({
      message: 'Password updated successfully',
      status: 'success',
    });
    render(<ResetPasswordForm />);

    await user.type(screen.getByLabelText('New password'), 'new-password');
    await user.type(screen.getByLabelText('Confirm password'), 'new-password');
    await user.click(screen.getByRole('button', { name: 'Update password' }));

    await waitFor(() => {
      expect(mocks.resetMutateAsync).toHaveBeenCalledWith({
        token: 'ABCDEFGHIJKLMN',
        new_password: 'new-password',
      });
    });
    expect(await screen.findByText('Password updated')).toBeInTheDocument();
  });

  it('rejects an incomplete reset link before rendering the form', () => {
    mocks.searchToken = 'short';

    render(<ResetPasswordForm />);

    expect(screen.getByText('Invalid reset link')).toBeInTheDocument();
    expect(screen.queryByLabelText('New password')).not.toBeInTheDocument();
  });
});
