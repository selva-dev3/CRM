import { useMutation, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

// Types
export interface LoginPayload {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  refresh_token?: string;
  expires_in?: number;
  user_id?: string;
  user?: {
    id: string;
    name: string;
    email: string;
    role: string;
    organization_id?: string;
    permissions?: string[];
  };
}

export interface RegisterPayload {
  name: string;
  email: string;
  password: string;
  organization_name: string;
}

export interface RegisterResponse {
  message: string;
  user_id?: string;
  org_id?: string;
  name?: string;
  email?: string;
  role?: string;
}

export interface ForgotPasswordPayload {
  email: string;
}

export interface ForgotPasswordResponse {
  message: string;
  status: string;
}

export interface ResetPasswordPayload {
  token: string;
  new_password: string;
}

export interface AcceptInvitePayload {
  token: string;
  name: string;
  password: string;
}

export interface AcceptInviteResponse {
  message: string;
  user_id: string;
  email: string;
  name: string;
  role: string;
  status: string;
}

// API Functions
export async function loginApi(payload: LoginPayload): Promise<LoginResponse> {
  return apiClient<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({
      email: payload.email.trim(),
      password: payload.password,
    }),
  });
}

export async function registerApi(payload: RegisterPayload): Promise<RegisterResponse> {
  return apiClient<RegisterResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      name: payload.name.trim(),
      email: payload.email.trim(),
      password: payload.password,
      organization_name: payload.organization_name.trim(),
    }),
  });
}

export async function forgotPasswordApi(payload: ForgotPasswordPayload): Promise<ForgotPasswordResponse> {
  return apiClient<ForgotPasswordResponse>('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email: payload.email.trim() }),
  });
}

export async function resetPasswordApi(payload: ResetPasswordPayload): Promise<{ message: string }> {
  return apiClient<{ message: string }>(`/auth/reset-password?token=${payload.token}&new_password=${payload.new_password}`, {
    method: 'POST',
  });
}

export async function acceptInviteApi(payload: AcceptInvitePayload): Promise<AcceptInviteResponse> {
  return apiClient<AcceptInviteResponse>('/auth/accept-invite', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// TanStack Query Mutations
export function useLoginMutation(
  options?: UseMutationOptions<LoginResponse, Error, LoginPayload>
) {
  return useMutation<LoginResponse, Error, LoginPayload>({
    mutationFn: loginApi,
    ...options,
  });
}

export function useRegisterMutation(
  options?: UseMutationOptions<RegisterResponse, Error, RegisterPayload>
) {
  return useMutation<RegisterResponse, Error, RegisterPayload>({
    mutationFn: registerApi,
    ...options,
  });
}

export function useForgotPasswordMutation(
  options?: UseMutationOptions<ForgotPasswordResponse, Error, ForgotPasswordPayload>
) {
  return useMutation<ForgotPasswordResponse, Error, ForgotPasswordPayload>({
    mutationFn: forgotPasswordApi,
    ...options,
  });
}

export function useAcceptInviteMutation(
  options?: UseMutationOptions<AcceptInviteResponse, Error, AcceptInvitePayload>
) {
  return useMutation<AcceptInviteResponse, Error, AcceptInvitePayload>({
    mutationFn: acceptInviteApi,
    ...options,
  });
}
