import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LoginForm } from './login-form';
import { ApiError } from '@/lib/api/client';

const mocks = vi.hoisted(() => ({
  getCurrentUserApi: vi.fn(),
  mutateAsync: vi.fn(),
  notifyAuthUserChanged: vi.fn(),
  replace: vi.fn(),
  useLoginMutation: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace }),
}));

vi.mock('@/lib/api', () => ({
  getCurrentUserApi: mocks.getCurrentUserApi,
  useLoginMutation: () => mocks.useLoginMutation(),
}));

vi.mock('@/hooks/use-has-permission', () => ({
  notifyAuthUserChanged: mocks.notifyAuthUserChanged,
}));

describe('LoginForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    mocks.getCurrentUserApi.mockRejectedValue(new Error('No active session'));
    mocks.useLoginMutation.mockReturnValue({
      isPending: false,
      mutateAsync: mocks.mutateAsync,
    });
  });

  it('shows inline validation and blocks an empty submission', async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.click(screen.getByRole('button', { name: 'Sign in to CRM' }));

    expect(await screen.findByText('Work email is required')).toBeInTheDocument();
    expect(screen.getByText('Password is required')).toBeInTheDocument();
    expect(mocks.mutateAsync).not.toHaveBeenCalled();
  });

  it('stores a remembered session and redirects after a valid login', async () => {
    const user = userEvent.setup();
    mocks.mutateAsync.mockResolvedValue({
      token_type: 'bearer',
      user: { id: 'user-1', name: 'Alex', email: 'alex@crm.com', role: 'Admin' },
    });
    render(<LoginForm />);

    await user.type(screen.getByLabelText('Work email'), ' alex@crm.com ');
    await user.type(screen.getByLabelText('Password'), 'secret');
    await user.click(screen.getByRole('checkbox', { name: 'Keep me signed in on this device' }));
    await user.click(screen.getByRole('button', { name: 'Sign in to CRM' }));

    await waitFor(() => {
      expect(mocks.mutateAsync).toHaveBeenCalledWith({
        email: 'alex@crm.com',
        password: 'secret',
        rememberMe: true,
      });
    });
    expect(localStorage.getItem('user')).toContain('alex@crm.com');
    expect(sessionStorage.getItem('user')).toContain('alex@crm.com');
    expect(mocks.notifyAuthUserChanged).toHaveBeenCalledOnce();
    expect(mocks.replace).toHaveBeenCalledWith('/dashboard');
  });

  it('requests and verifies a two-factor code before redirecting', async () => {
    const user = userEvent.setup();
    mocks.mutateAsync
      .mockRejectedValueOnce(
        new ApiError('Enter the authentication code', 'http', 428, 'TWO_FACTOR_REQUIRED'),
      )
      .mockResolvedValueOnce({
        token_type: 'bearer',
        user: { id: 'user-1', name: 'Alex', email: 'alex@crm.com', role: 'Admin' },
      });
    render(<LoginForm />);

    await user.type(screen.getByLabelText('Work email'), 'alex@crm.com');
    await user.type(screen.getByLabelText('Password'), 'secret');
    await user.click(screen.getByRole('button', { name: 'Sign in to CRM' }));

    const code = await screen.findByLabelText('Authentication code');
    await user.type(code, '123456');
    await user.click(screen.getByRole('button', { name: 'Sign in to CRM' }));

    expect(mocks.mutateAsync).toHaveBeenLastCalledWith({
      email: 'alex@crm.com',
      password: 'secret',
      rememberMe: false,
      twoFactorCode: '123456',
    });
    expect(mocks.replace).toHaveBeenCalledWith('/dashboard');
  });

  it('keeps entered credentials and shows a server error', async () => {
    const user = userEvent.setup();
    mocks.mutateAsync.mockRejectedValue(new Error('Invalid email or password'));
    render(<LoginForm />);

    const email = screen.getByLabelText('Work email');
    await user.type(email, 'alex@crm.com');
    await user.type(screen.getByLabelText('Password'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: 'Sign in to CRM' }));

    expect(await screen.findByText('Invalid email or password')).toBeInTheDocument();
    expect(email).toHaveValue('alex@crm.com');
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it('provides an accessible password visibility control', async () => {
    const user = userEvent.setup();
    render(<LoginForm />);
    const password = screen.getByLabelText('Password');

    expect(password).toHaveAttribute('type', 'password');
    await user.click(screen.getByRole('button', { name: 'Show password' }));
    expect(password).toHaveAttribute('type', 'text');
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('disables submission while authentication is pending', () => {
    mocks.useLoginMutation.mockReturnValue({
      isPending: true,
      mutateAsync: mocks.mutateAsync,
    });

    render(<LoginForm />);

    expect(screen.getByRole('button', { name: 'Signing in…' })).toBeDisabled();
  });
});
