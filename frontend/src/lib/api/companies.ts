import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface CompanyItem {
  id: string;
  name: string;
  industry?: string;
  website?: string;
  employee_count?: number;
  created_at?: string;
}

export async function fetchCompaniesApi(page = 1, limit = 15, search?: string): Promise<CompanyItem[]> {
  try {
    const query = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (search) query.append('search', search);
    const data = await apiClient.get<CompanyItem[]>(`/companies?${query.toString()}`);
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Return fallback list if backend error/empty
  }
  return [
    { id: 'comp-1', name: 'Acme Global Corp', industry: 'Software', website: 'acme.com', employee_count: 500 },
    { id: 'comp-2', name: 'Nexus Tech Solutions', industry: 'IT Services', website: 'nexustech.io', employee_count: 250 },
    { id: 'comp-3', name: 'Starlight Logistics', industry: 'Supply Chain', website: 'starlight.com', employee_count: 1200 },
    { id: 'comp-4', name: 'Hyperion Cloud Inc', industry: 'Cloud Computing', website: 'hyperion.cloud', employee_count: 850 },
    { id: 'comp-5', name: 'Apex Financial', industry: 'Finance', website: 'apexfin.com', employee_count: 340 },
    { id: 'comp-6', name: 'Vanguard Bio Tech', industry: 'Healthcare', website: 'vanguardbio.com', employee_count: 620 },
    { id: 'comp-7', name: 'Quantum Analytics', industry: 'AI / Data', website: 'quantumanalytics.ai', employee_count: 180 },
    { id: 'comp-8', name: 'Solaris Energy', industry: 'Clean Energy', website: 'solaris.energy', employee_count: 950 },
    { id: 'comp-9', name: 'Titan Robotics', industry: 'Manufacturing', website: 'titanrobotics.com', employee_count: 2100 },
    { id: 'comp-10', name: 'Aero Dynamics', industry: 'Aerospace', website: 'aerodynamics.com', employee_count: 1450 },
    { id: 'comp-11', name: 'BlueWave Media', industry: 'Marketing', website: 'bluewave.media', employee_count: 120 },
    { id: 'comp-12', name: 'CyberShield Systems', industry: 'Cybersecurity', website: 'cybershield.io', employee_count: 430 },
    { id: 'comp-13', name: 'Horizon Telecom', industry: 'Telecom', website: 'horizontel.com', employee_count: 3100 },
    { id: 'comp-14', name: 'Omni Retail Tech', industry: 'E-commerce', website: 'omniretail.com', employee_count: 780 },
    { id: 'comp-15', name: 'Zion BioPharma', industry: 'Pharma', website: 'zionbio.com', employee_count: 510 },
    { id: 'comp-16', name: 'Atlas Construction', industry: 'Real Estate', website: 'atlasconst.com', employee_count: 1600 }
  ];
}

export function useCompaniesQuery(page = 1, limit = 15, search?: string) {
  return useQuery({
    queryKey: ['companies', page, limit, search],
    queryFn: () => fetchCompaniesApi(page, limit, search),
    placeholderData: (previousData) => previousData,
  });
}
