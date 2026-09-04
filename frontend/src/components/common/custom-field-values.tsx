import type { CustomFieldDefinition, CustomFieldValue } from '@/lib/api/custom-fields';

interface CustomFieldValuesProps {
  fields: CustomFieldDefinition[];
  values: Record<string, CustomFieldValue>;
}

function formatCustomFieldValue(value: CustomFieldValue): string {
  if (value === null || value === undefined || value === '') return 'Not provided';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

export function CustomFieldValues({ fields, values }: CustomFieldValuesProps) {
  if (fields.length === 0) return null;

  return (
    <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
      <h2 className="text-sm font-bold text-slate-900">Custom Fields</h2>
      <div className="grid grid-cols-1 gap-4 text-xs sm:grid-cols-2 md:grid-cols-4">
        {fields.map((field) => (
          <div
            key={field.field_name}
            className="space-y-1 rounded-xl border border-slate-100 bg-slate-50 p-3"
          >
            <span className="font-medium text-slate-500">{field.label}</span>
            <span className="block font-semibold text-slate-900">
              {formatCustomFieldValue(values[field.field_name])}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
