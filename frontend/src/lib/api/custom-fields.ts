import { useQuery } from '@tanstack/react-query';

import { apiClient } from '@/lib/api/client';

export type CustomFieldValue = string | number | boolean | null;
export type CustomFieldEntity = 'Lead' | 'Contact' | 'Company' | 'Deal';

export interface CustomFieldDefinition {
  field_name: string;
  field_type: 'text' | 'number' | 'boolean' | 'select';
  label: string;
  options: string[];
}

const ENTITY_ENDPOINTS: Record<CustomFieldEntity, string> = {
  Lead: '/leads/custom-fields',
  Contact: '/contacts/custom-fields',
  Company: '/companies/custom-fields',
  Deal: '/deals/custom-fields',
};

export const customFieldKeys = {
  all: ['entity-custom-fields'] as const,
  entity: (entity: CustomFieldEntity) => [...customFieldKeys.all, entity] as const,
};

export async function fetchEntityCustomFieldsApi(
  entity: CustomFieldEntity,
): Promise<CustomFieldDefinition[]> {
  return apiClient.get<CustomFieldDefinition[]>(ENTITY_ENDPOINTS[entity]);
}

export function useEntityCustomFieldsQuery(entity: CustomFieldEntity, enabled = true) {
  return useQuery({
    queryKey: customFieldKeys.entity(entity),
    queryFn: () => fetchEntityCustomFieldsApi(entity),
    enabled,
  });
}
