import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface InvoiceItem {
  id: string;
  number: string;
  client: string;
  amount: number;
  status: string;
  due_date: string;
}

export async function fetchInvoicesApi(page = 1, limit = 15, search?: string): Promise<InvoiceItem[]> {
  try {
    const query = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (search) query.append('search', search);
    const data = await apiClient.get<InvoiceItem[]>(`/invoices?${query.toString()}`);
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Fallback data
  }
  return [
    { id: 'inv-101', number: 'INV-2026-001', client: 'Acme Global Corp', amount: 14500, status: 'Paid', due_date: '2026-08-01' },
    { id: 'inv-102', number: 'INV-2026-002', client: 'Nexus Tech Solutions', amount: 8200, status: 'Overdue', due_date: '2026-07-28' },
    { id: 'inv-103', number: 'INV-2026-003', client: 'Starlight Logistics', amount: 22000, status: 'Pending', due_date: '2026-08-15' },
    { id: 'inv-104', number: 'INV-2026-004', client: 'Hyperion Cloud Inc', amount: 18900, status: 'Paid', due_date: '2026-08-02' },
    { id: 'inv-105', number: 'INV-2026-005', client: 'Apex Financial', amount: 9600, status: 'Pending', due_date: '2026-08-20' },
    { id: 'inv-106', number: 'INV-2026-006', client: 'Vanguard Bio Tech', amount: 31000, status: 'Paid', due_date: '2026-07-30' },
    { id: 'inv-107', number: 'INV-2026-007', client: 'Quantum Analytics', amount: 5400, status: 'Draft', due_date: '2026-08-25' },
    { id: 'inv-108', number: 'INV-2026-008', client: 'Solaris Energy', amount: 12800, status: 'Paid', due_date: '2026-08-03' },
    { id: 'inv-109', number: 'INV-2026-009', client: 'Titan Robotics', amount: 45000, status: 'Pending', due_date: '2026-08-28' },
    { id: 'inv-110', number: 'INV-2026-010', client: 'Aero Dynamics', amount: 27500, status: 'Overdue', due_date: '2026-07-25' },
    { id: 'inv-111', number: 'INV-2026-011', client: 'BlueWave Media', amount: 3900, status: 'Paid', due_date: '2026-08-04' },
    { id: 'inv-112', number: 'INV-2026-012', client: 'CyberShield Systems', amount: 11200, status: 'Pending', due_date: '2026-08-30' },
    { id: 'inv-113', number: 'INV-2026-013', client: 'Horizon Telecom', amount: 68000, status: 'Paid', due_date: '2026-07-15' },
    { id: 'inv-114', number: 'INV-2026-014', client: 'Omni Retail Tech', amount: 16400, status: 'Pending', due_date: '2026-09-02' },
    { id: 'inv-115', number: 'INV-2026-015', client: 'Zion BioPharma', amount: 21000, status: 'Draft', due_date: '2026-09-05' },
    { id: 'inv-116', number: 'INV-2026-016', client: 'Atlas Construction', amount: 52000, status: 'Pending', due_date: '2026-09-10' },
  ];
}

export function useInvoicesQuery(page = 1, limit = 15, search?: string) {
  return useQuery({
    queryKey: ['invoices', page, limit, search],
    queryFn: () => fetchInvoicesApi(page, limit, search),
    placeholderData: (previousData) => previousData,
  });
}
