import { CustomFields } from '@/components/common/custom-fields';
import type { CustomFieldDefinition, CustomFieldValue } from '@/lib/api/custom-fields';

interface DealCustomFieldsProps {
  fields: CustomFieldDefinition[];
  values: Record<string, CustomFieldValue>;
  onChange: (fieldName: string, value: CustomFieldValue) => void;
  isLoading: boolean;
  isError: boolean;
}

export function DealCustomFields({
  fields,
  values,
  onChange,
  isLoading,
  isError,
}: DealCustomFieldsProps) {
  return (
    <CustomFields
      fields={fields}
      values={values}
      onChange={onChange}
      isLoading={isLoading}
      isError={isError}
      idPrefix="deal"
    />
  );
}
