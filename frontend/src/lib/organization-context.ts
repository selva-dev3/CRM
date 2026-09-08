/** Tab-local selection, authorized independently by the backend on every request. */
const CONTEXT_KEY = 'crm:organization-context';
export const ORGANIZATION_DELETED_EVENT = 'crm:organization-deleted';
export const ORGANIZATION_DELETED_BROADCAST = 'crm:organization-deleted-broadcast';

export function broadcastOrganizationDeleted(organizationId: string): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(ORGANIZATION_DELETED_EVENT, { detail: organizationId }));
  localStorage.setItem(ORGANIZATION_DELETED_BROADCAST, JSON.stringify({ organizationId, time: Date.now() }));
}

export function getOrganizationContext(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(CONTEXT_KEY);
}

export function setOrganizationContext(organizationId: string | null): void {
  if (typeof window === 'undefined') return;
  if (organizationId) sessionStorage.setItem(CONTEXT_KEY, organizationId);
  else sessionStorage.removeItem(CONTEXT_KEY);
}

const LAST_DELETION_KEY = 'crm:last-organization-deletion';

export function rememberOrganizationDeletion(operationId: string): void {
  if (typeof window !== 'undefined') sessionStorage.setItem(LAST_DELETION_KEY, operationId);
}

export function getLastOrganizationDeletion(): string | null {
  if (typeof window === 'undefined') return null;
  const value = sessionStorage.getItem(LAST_DELETION_KEY);
  return value && /^[0-9a-f-]{36}$/i.test(value) ? value : null;
}
