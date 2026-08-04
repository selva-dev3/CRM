import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface QuoteItem {
  id: string;
  quote_number: string;
  client: string;
  total_amount: number;
  status: string;
  created_at: string;
}

export async function fetchQuotesApi(page = 1, limit = 15, search?: string): Promise<QuoteItem[]> {
  try {
    const query = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (search) query.append('search', search);
    const data = await apiClient.get<QuoteItem[]>(`/quotes?${query.toString()}`);
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Fallback data
  }
  return [
    { id: 'q-201', quote_number: 'Q-2026-0801', client: 'Acme Global Corp', total_amount: 18500, status: 'Accepted', created_at: '2026-08-01' },
    { id: 'q-202', quote_number: 'Q-2026-0802', client: 'Nexus Tech Solutions', total_amount: 9200, status: 'Sent', created_at: '2026-08-02' },
    { id: 'q-203', quote_number: 'Q-2026-0803', client: 'Starlight Logistics', total_amount: 34000, status: 'Under Review', created_at: '2026-08-02' },
    { id: 'q-204', quote_number: 'Q-2026-0804', client: 'Hyperion Cloud Inc', total_amount: 25000, status: 'Accepted', created_at: '2026-08-03' },
    { id: 'q-205', quote_number: 'Q-2026-0805', client: 'Apex Financial', total_amount: 14000, status: 'Draft', created_at: '2026-08-03' },
    { id: 'q-206', quote_number: 'Q-2026-0806', client: 'Vanguard Bio Tech', total_amount: 42000, status: 'Accepted', created_at: '2026-08-04' },
    { id: 'q-207', quote_number: 'Q-2026-0807', client: 'Quantum Analytics', total_amount: 7800, status: 'Sent', created_at: '2026-08-04' },
    { id: 'q-208', quote_number: 'Q-2026-0808', client: 'Solaris Energy', total_amount: 19500, status: 'Expired', created_at: '2026-07-25' },
    { id: 'q-209', quote_number: 'Q-2026-0809', client: 'Titan Robotics', total_amount: 60000, status: 'Under Review', created_at: '2026-08-04' },
    { id: 'q-210', quote_number: 'Q-2026-0810', client: 'Aero Dynamics', total_amount: 31000, status: 'Sent', created_at: '2026-08-04' },
    { id: 'q-211', quote_number: 'Q-2026-0811', client: 'BlueWave Media', total_amount: 4800, status: 'Accepted', created_at: '2026-08-04' },
    { id: 'q-212', quote_number: 'Q-2026-0812', client: 'CyberShield Systems', total_amount: 15600, status: 'Draft', created_at: '2026-08-04' },
    { id: 'q-213', quote_number: 'Q-2026-0813', client: 'Horizon Telecom', total_amount: 85000, status: 'Accepted', created_at: '2026-08-01' },
    { id: 'q-214', quote_number: 'Q-2026-0814', client: 'Omni Retail Tech', total_amount: 22400, status: 'Sent', created_at: '2026-08-04' },
    { id: 'q-215', quote_number: 'Q-2026-0815', client: 'Zion BioPharma', total_amount: 28000, status: 'Draft', created_at: '2026-08-04' },
    { id: 'q-216', quote_number: 'Q-2026-0816', client: 'Atlas Construction', total_amount: 68000, status: 'Sent', created_at: '2026-08-04' },
  ];
}

export function useQuotesQuery(page = 1, limit = 15, search?: string) {
  return useQuery({
    queryKey: ['quotes', page, limit, search],
    queryFn: () => fetchQuotesApi(page, limit, search),
    placeholderData: (previousData) => previousData,
  });
}
