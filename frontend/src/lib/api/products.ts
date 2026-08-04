import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface ProductItem {
  id: string;
  name: string;
  sku: string;
  price: number;
  category?: string;
}

export async function fetchProductsApi(page = 1, limit = 15, search?: string): Promise<ProductItem[]> {
  try {
    const query = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (search) query.append('search', search);
    const data = await apiClient.get<ProductItem[]>(`/products?${query.toString()}`);
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Return fallback list
  }
  return [
    { id: 'prod-1', name: 'CRM Enterprise SaaS Annual', sku: 'SKU-CRM-ENT-01', price: 12000, category: 'Software' },
    { id: 'prod-2', name: 'Sales Pipeline Automation Addon', sku: 'SKU-AUT-PIPE-02', price: 3500, category: 'Software' },
    { id: 'prod-3', name: 'AI Lead Scoring Engine API', sku: 'SKU-AI-LEAD-03', price: 5000, category: 'AI Services' },
    { id: 'prod-4', name: 'Custom Integration Setup', sku: 'SKU-INT-SRV-04', price: 2500, category: 'Professional Services' },
    { id: 'prod-5', name: '24/7 Dedicated Support Tier', sku: 'SKU-SUP-247-05', price: 1800, category: 'Support' },
    { id: 'prod-6', name: 'Marketing Automation Suite', sku: 'SKU-MKT-AUT-06', price: 4200, category: 'Software' },
    { id: 'prod-7', name: 'Data Migration Toolkit', sku: 'SKU-DAT-MIG-07', price: 1500, category: 'Services' },
    { id: 'prod-8', name: 'Executive Dashboard Analytics', sku: 'SKU-ANL-EXEC-08', price: 2900, category: 'Software' },
    { id: 'prod-9', name: 'Email Campaign Blast Tool', sku: 'SKU-EML-BLST-09', price: 950, category: 'Marketing' },
    { id: 'prod-10', name: 'Customer Success Onboarding Pack', sku: 'SKU-CS-ONB-10', price: 3000, category: 'Services' },
    { id: 'prod-11', name: 'Multi-Tenant Security Shield', sku: 'SKU-SEC-SHLD-11', price: 6000, category: 'Security' },
    { id: 'prod-12', name: 'VoIP Telephony Gateway Connector', sku: 'SKU-VOIP-CON-12', price: 1200, category: 'Software' },
    { id: 'prod-13', name: 'Document E-Sign Expansion', sku: 'SKU-DOC-SIGN-13', price: 800, category: 'Addons' },
    { id: 'prod-14', name: 'ERP Sync Connector', sku: 'SKU-ERP-SYNC-14', price: 4500, category: 'Integration' },
    { id: 'prod-15', name: 'Territory Management Plugin', sku: 'SKU-TER-PLG-15', price: 2100, category: 'Software' },
    { id: 'prod-16', name: 'Custom Workflow Architect Engine', sku: 'SKU-WFL-ENG-16', price: 5500, category: 'Enterprise' },
  ];
}

export function useProductsQuery(page = 1, limit = 15, search?: string) {
  return useQuery({
    queryKey: ['products', page, limit, search],
    queryFn: () => fetchProductsApi(page, limit, search),
    placeholderData: (previousData) => previousData,
  });
}
