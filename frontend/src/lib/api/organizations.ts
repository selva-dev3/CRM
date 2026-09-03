import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { notifyAuthUserChanged } from '@/hooks/use-has-permission';

export interface OrganizationItem {
  id: string;
  name: string;
  slug?: string;
  email?: string;
  phone?: string;
  website?: string;
  industry?: string;
  company_size?: string;
  country?: string;
  state?: string;
  city?: string;
  address?: string;
  postal_code?: string;
  timezone?: string;
  currency?: string;
  language?: string;
  logo_url?: string;
  tax_number?: string;
  registration_number?: string;
  status?: string;
  domain?: string;
  plan?: string;
  max_users?: number;
  created_at?: string;
  members_count?: number;
}

export interface CreateOrganizationPayload {
  name: string;
  slug?: string;
  email?: string;
  phone?: string;
  website?: string;
  industry?: string;
  company_size?: string;
  country?: string;
  state?: string;
  city?: string;
  address?: string;
  postal_code?: string;
  timezone?: string;
  currency?: string;
  language?: string;
  logo_url?: string;
  tax_number?: string;
  registration_number?: string;
  status?: string;
  domain?: string;
  plan?: string;
  max_users?: number;
}

export interface UpdateOrganizationPayload {
  name?: string;
  slug?: string;
  email?: string;
  phone?: string;
  website?: string;
  industry?: string;
  company_size?: string;
  country?: string;
  state?: string;
  city?: string;
  address?: string;
  postal_code?: string;
  timezone?: string;
  currency?: string;
  language?: string;
  logo_url?: string;
  tax_number?: string;
  registration_number?: string;
  status?: string;
  domain?: string;
  plan?: string;
  max_users?: number;
}

export interface SubscriptionPlanItem {
  id: string;
  name: string;
  slug: string;
  price_monthly: number;
  price_yearly: number;
  max_users: number;
  max_storage_gb: number;
  ai_credits: number;
  features: string[];
  is_active?: boolean;
}

export interface OrganizationSubscription {
  plan: string;
  plan_slug?: string;
  billing_cycle: string;
  amount: number;
  next_billing: string;
}

export interface CreateSubscriptionCheckoutPayload {
  plan_slug: string;
  org_id?: string;
}

export interface SubscriptionCheckoutResponse {
  checkout_url: string;
  session_id: string;
  status: string;
}

export interface SubscriptionCheckoutVerifyResponse {
  verified: boolean;
  db_synced: boolean;
  plan: string | null;
  plan_slug: string | null;
  status: string;
  message: string;
}

export interface OrganizationUsage {
  users_used: number;
  users_limit: number;
  storage_gb_used: number;
  storage_gb_limit: number;
}

export interface OrganizationMember {
  id: string;
  name: string;
  email: string;
  role: string;
  status?: string;
  joined_at?: string;
}

export interface OrganizationDomain {
  id: string;
  domain: string;
  status: 'verified' | 'pending' | 'failed';
  verified_at?: string;
}

export interface OrganizationAuditLog {
  id: string;
  action: string;
  actor: string;
  timestamp: string;
  ip?: string;
}

// 1. GET /api/v1/organizations (Get current organization)
export async function getCurrentOrganizationApi(): Promise<OrganizationItem> {
  return apiClient.get<OrganizationItem>('/organizations');
}

// 2. GET /api/v1/organizations/{org_id} (Get organization by ID)
export async function fetchOrganizationByIdApi(id: string): Promise<OrganizationItem> {
  return apiClient.get<OrganizationItem>(`/organizations/${id}`);
}

// 3. PUT /api/v1/organizations/{org_id} (Update organization by ID)
export async function updateOrganizationApi(id: string, payload: UpdateOrganizationPayload): Promise<OrganizationItem> {
  return apiClient.put<OrganizationItem>(`/organizations/${id}`, payload);
}

// 3b. DELETE /api/v1/organizations/{org_id} (Delete organization by ID)
export async function deleteOrganizationApi(id: string): Promise<{ message: string; status: string }> {
  return apiClient.delete<{ message: string; status: string }>(`/organizations/${id}`);
}

// 4. GET /api/v1/organizations/members (List members)
export async function getOrganizationMembersApi(): Promise<OrganizationMember[]> {
  return apiClient.get<OrganizationMember[]>('/organizations/members');
}

// 5. DELETE /api/v1/organizations/members/{user_id} (Remove member)
export async function removeOrganizationMemberApi(userId: string): Promise<{ message: string; status: string }> {
  return apiClient.delete<{ message: string; status: string }>(`/organizations/members/${userId}`);
}

// 6. GET /api/v1/organizations/subscription (Subscription details)
export async function getOrganizationSubscriptionApi(): Promise<OrganizationSubscription> {
  return apiClient.get<OrganizationSubscription>('/organizations/subscription');
}

// 6b. GET /api/v1/organizations/subscription/plans (List available plans)
export async function getSubscriptionPlansApi(): Promise<SubscriptionPlanItem[]> {
  return apiClient.get<SubscriptionPlanItem[]>('/organizations/subscription/plans');
}

// 7. POST /api/v1/organizations/subscription/upgrade (Upgrade plan)
export async function upgradeOrganizationSubscriptionApi(planSlug: string): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/organizations/subscription/upgrade?plan_slug=${encodeURIComponent(planSlug)}`);
}

// 7b. POST /api/v1/organizations/subscription/checkout (Create Stripe checkout session)
export async function createSubscriptionCheckoutApi(payload: CreateSubscriptionCheckoutPayload): Promise<SubscriptionCheckoutResponse> {
  return apiClient.post<SubscriptionCheckoutResponse>('/organizations/subscription/checkout', payload);
}

// 7c. GET /api/v1/organizations/subscription/checkout/verify (Verify Stripe checkout session)
export async function verifySubscriptionCheckoutApi(sessionId: string, orgId?: string): Promise<SubscriptionCheckoutVerifyResponse> {
  const url = orgId
    ? `/organizations/subscription/checkout/verify?session_id=${encodeURIComponent(sessionId)}&org_id=${encodeURIComponent(orgId)}`
    : `/organizations/subscription/checkout/verify?session_id=${encodeURIComponent(sessionId)}`;
  return apiClient.get<SubscriptionCheckoutVerifyResponse>(url);
}

// 8. POST /api/v1/organizations/subscription/cancel (Cancel subscription)
export async function cancelOrganizationSubscriptionApi(): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>('/organizations/subscription/cancel');
}

// 9. GET /api/v1/organizations/usage (Get usage metrics & quotas)
export async function getOrganizationUsageApi(): Promise<OrganizationUsage> {
  return apiClient.get<OrganizationUsage>('/organizations/usage');
}

// 10. POST /api/v1/organizations/branding (Update branding & upload logo to S3)
export async function updateOrganizationBrandingApi(formData: FormData): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>('/organizations/branding', formData);
}

// 11. POST /api/v1/organizations/domains/verify (Verify domain TXT record)
export async function verifyOrganizationDomainApi(domain: string): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/organizations/domains/verify?domain=${encodeURIComponent(domain)}`);
}

// 12. GET /api/v1/organizations/domains (List custom domains)
export async function getOrganizationDomainsApi(): Promise<OrganizationDomain[]> {
  return apiClient.get<OrganizationDomain[]>('/organizations/domains');
}

// 13. GET /api/v1/organizations/audit-logs (Get audit logs)
export async function getOrganizationAuditLogsApi(): Promise<OrganizationAuditLog[]> {
  return apiClient.get<OrganizationAuditLog[]>('/organizations/audit-logs');
}

// 14. POST /api/v1/organizations/transfer-ownership (Transfer ownership)
export async function transferOrganizationOwnershipApi(newOwnerUserId: string): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/organizations/transfer-ownership?new_owner_user_id=${encodeURIComponent(newOwnerUserId)}`);
}

// React Query Hooks
export function useCurrentOrganizationQuery() {
  return useQuery({
    queryKey: ['current-organization'],
    queryFn: getCurrentOrganizationApi,
  });
}

export function useOrganizationByIdQuery(id: string) {
  return useQuery({
    queryKey: ['organization', id],
    queryFn: () => fetchOrganizationByIdApi(id),
    enabled: Boolean(id),
  });
}

export function useUpdateOrganizationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateOrganizationPayload }) => updateOrganizationApi(id, payload),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['organizations'] });
      queryClient.invalidateQueries({ queryKey: ['current-organization'] });
      queryClient.invalidateQueries({ queryKey: ['organization', id] });
    },
  });
}

export function useOrganizationMembersQuery() {
  return useQuery({
    queryKey: ['organization-members'],
    queryFn: getOrganizationMembersApi,
  });
}

export function useRemoveOrganizationMemberMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: removeOrganizationMemberApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organization-members'] });
    },
  });
}

export function useOrganizationSubscriptionQuery() {
  return useQuery({
    queryKey: ['organization-subscription'],
    queryFn: getOrganizationSubscriptionApi,
  });
}

export function useCreateSubscriptionCheckoutMutation() {
  return useMutation({
    mutationFn: createSubscriptionCheckoutApi,
  });
}

export function useVerifySubscriptionCheckoutQuery(sessionId: string | null, orgId?: string | null) {
  return useQuery({
    queryKey: ['subscription-checkout-verify', sessionId, orgId],
    queryFn: () => verifySubscriptionCheckoutApi(sessionId!, orgId || undefined),
    enabled: Boolean(sessionId && sessionId.trim().length > 0),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && data.verified && !data.db_synced) {
        return 2000;
      }
      return false;
    },
    retry: 2,
  });
}

export function useCancelSubscriptionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cancelOrganizationSubscriptionApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organization-subscription'] });
    },
  });
}

export function useOrganizationUsageQuery() {
  return useQuery({
    queryKey: ['organization-usage'],
    queryFn: getOrganizationUsageApi,
  });
}

export function useUpdateBrandingMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateOrganizationBrandingApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['current-organization'] });
    },
  });
}

export function useVerifyDomainMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: verifyOrganizationDomainApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organization-domains'] });
    },
  });
}

export function useOrganizationDomainsQuery() {
  return useQuery({
    queryKey: ['organization-domains'],
    queryFn: getOrganizationDomainsApi,
  });
}

export function useOrganizationAuditLogsQuery() {
  return useQuery({
    queryKey: ['organization-audit-logs'],
    queryFn: getOrganizationAuditLogsApi,
  });
}

export function useTransferOwnershipMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: transferOrganizationOwnershipApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['current-organization'] });
      queryClient.invalidateQueries({ queryKey: ['organization-members'] });
    },
  });
}

export function useSubscriptionPlansQuery() {
  return useQuery({
    queryKey: ['subscription-plans'],
    queryFn: getSubscriptionPlansApi,
  });
}

export function useDeleteOrganizationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteOrganizationApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organizations'] });
      queryClient.invalidateQueries({ queryKey: ['current-organization'] });
    },
  });
}

// Organization Invitations API
export interface ValidateInvitationResponse {
  organization?: {
    id: string;
    name: string;
    slug?: string;
    domain?: string;
    plan?: string;
    status?: string;
  };
  email: string;
  full_name?: string;
  role: string;
  expires_at: string;
  status: string;
  is_valid: boolean;
}

export interface InviteNewOrganizationPayload {
  email: string;
  full_name: string;
}

export interface InviteNewOrganizationResponse {
  organization: {
    id: string;
    name: string;
    slug?: string;
    domain?: string;
    email?: string;
    status?: string;
    plan?: string;
    max_users?: number;
  };
  invitation: {
    id: string;
    organization_id?: string;
    organization_name?: string;
    email: string;
    full_name?: string;
    role?: string;
    token: string;
    status: string;
    expires_at: string;
    invite_url?: string;
  };
  message: string;
}

export interface AcceptInvitationPayload {
  password: string;
  full_name?: string;
  organization_name?: string;
  domain?: string;
  industry?: string;
  country?: string;
  city?: string;
  phone?: string;
}

export interface AcceptInvitationResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    name: string;
    email: string;
    role: string;
    organization_id: string;
    is_active: boolean;
  };
  organization?: {
    id: string;
    name: string;
    slug?: string;
    domain?: string;
    plan?: string;
  };
  message: string;
}

export async function validateInvitationApi(token: string): Promise<ValidateInvitationResponse> {
  return apiClient.get<ValidateInvitationResponse>(`/organizations/invitations/${encodeURIComponent(token)}`);
}

export async function acceptInvitationApi({ token, payload }: { token: string; payload: AcceptInvitationPayload }): Promise<AcceptInvitationResponse> {
  return apiClient.post<AcceptInvitationResponse>(`/organizations/invitations/${encodeURIComponent(token)}/accept`, payload);
}

export async function inviteNewOrganizationApi(payload: InviteNewOrganizationPayload): Promise<InviteNewOrganizationResponse> {
  return apiClient.post<InviteNewOrganizationResponse>('/organizations/invitations/new-organization', payload);
}

export function useValidateInvitationQuery(token: string) {
  return useQuery({
    queryKey: ['validate-invitation', token],
    queryFn: () => validateInvitationApi(token),
    enabled: Boolean(token),
    retry: false,
  });
}

export function useAcceptInvitationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: acceptInvitationApi,
    onSuccess: (data) => {
      if (data.user) {
        localStorage.setItem('user', JSON.stringify(data.user));
        notifyAuthUserChanged();
      }
      queryClient.invalidateQueries({ queryKey: ['current-organization'] });
    },
  });
}

export function useInviteNewOrganizationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: inviteNewOrganizationApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organizations'] });
      queryClient.invalidateQueries({ queryKey: ['current-organization'] });
    },
  });
}
