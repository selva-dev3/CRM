/** Tab-local selection, authorized independently by the backend on every request. */
const CONTEXT_KEY = 'crm:organization-context';

export function getOrganizationContext(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(CONTEXT_KEY);
}

export function setOrganizationContext(organizationId: string | null): void {
  if (typeof window === 'undefined') return;
  if (organizationId) sessionStorage.setItem(CONTEXT_KEY, organizationId);
  else sessionStorage.removeItem(CONTEXT_KEY);
}
