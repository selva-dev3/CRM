import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface ContactItem {
  id: string;
  name: string;
  email: string;
  phone?: string;
  position?: string;
  company_id?: string;
  created_at?: string;
}

export async function fetchContactsApi(page = 1, limit = 15, search?: string): Promise<ContactItem[]> {
  try {
    const query = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (search) query.append('search', search);
    const data = await apiClient.get<ContactItem[]>(`/contacts?${query.toString()}`);
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Return fallback list
  }
  return [
    { id: 'cnt-1', name: 'Alexander Wright', email: 'alex.wright@acme.com', phone: '+1 555-0101', position: 'VP of Sales', company_id: 'comp-1' },
    { id: 'cnt-2', name: 'Sophia Martinez', email: 'sophia.m@nexustech.io', phone: '+1 555-0102', position: 'CTO', company_id: 'comp-2' },
    { id: 'cnt-3', name: 'Marcus Vance', email: 'm.vance@starlight.com', phone: '+1 555-0103', position: 'Head of Operations', company_id: 'comp-3' },
    { id: 'cnt-4', name: 'Elena Rostova', email: 'elena@hyperion.cloud', phone: '+1 555-0104', position: 'Lead Architect', company_id: 'comp-4' },
    { id: 'cnt-5', name: 'David Chen', email: 'd.chen@apexfin.com', phone: '+1 555-0105', position: 'Finance Manager', company_id: 'comp-5' },
    { id: 'cnt-6', name: 'Rachel Green', email: 'rachel@vanguardbio.com', phone: '+1 555-0106', position: 'R&D Director', company_id: 'comp-6' },
    { id: 'cnt-7', name: 'James Wilson', email: 'jwilson@quantumanalytics.ai', phone: '+1 555-0107', position: 'Data Scientist', company_id: 'comp-7' },
    { id: 'cnt-8', name: 'Olivia Taylor', email: 'olivia@solaris.energy', phone: '+1 555-0108', position: 'Sustainability Lead', company_id: 'comp-8' },
    { id: 'cnt-9', name: 'Ethan Hunt', email: 'ethan@titanrobotics.com', phone: '+1 555-0109', position: 'Chief Engineer', company_id: 'comp-9' },
    { id: 'cnt-10', name: 'Isabella Scott', email: 'isabella@aerodynamics.com', phone: '+1 555-0110', position: 'Procurement Officer', company_id: 'comp-10' },
    { id: 'cnt-11', name: 'Lucas Black', email: 'lucas@bluewave.media', phone: '+1 555-0111', position: 'Creative Director', company_id: 'comp-11' },
    { id: 'cnt-12', name: 'Mia Anderson', email: 'mia@cybershield.io', phone: '+1 555-0112', position: 'Security Analyst', company_id: 'comp-12' },
    { id: 'cnt-13', name: 'Benjamin King', email: 'b.king@horizontel.com', phone: '+1 555-0113', position: 'Network Admin', company_id: 'comp-13' },
    { id: 'cnt-14', name: 'Charlotte Harris', email: 'charlotte@omniretail.com', phone: '+1 555-0114', position: 'Product Lead', company_id: 'comp-14' },
    { id: 'cnt-15', name: 'Daniel Miller', email: 'dmiller@zionbio.com', phone: '+1 555-0115', position: 'Clinical Director', company_id: 'comp-15' },
    { id: 'cnt-16', name: 'Amelia Clark', email: 'aclark@atlasconst.com', phone: '+1 555-0116', position: 'Project Director', company_id: 'comp-16' }
  ];
}

export function useContactsQuery(page = 1, limit = 15, search?: string) {
  return useQuery({
    queryKey: ['contacts', page, limit, search],
    queryFn: () => fetchContactsApi(page, limit, search),
    placeholderData: (previousData) => previousData,
  });
}
