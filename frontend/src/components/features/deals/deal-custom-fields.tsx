import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { DealCustomFieldDefinition } from '@/lib/api/deals';

type CustomFieldValue = string | number | boolean | null;

interface DealCustomFieldsProps {
  fields: DealCustomFieldDefinition[];
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
  if (isLoading) {
    return <p className="text-xs text-slate-500">Loading custom fields...</p>;
  }
  if (isError) {
    return <p className="text-xs text-rose-600">Custom fields are unavailable.</p>;
  }
  if (fields.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3 border-t border-slate-100 pt-4">
      <h4 className="font-semibold text-slate-700">Custom Fields</h4>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {fields.map((field) => {
          const value = values[field.field_name];
          const inputId = `deal-custom-${field.field_name}`;
          if (field.field_type === 'boolean') {
            return (
              <label key={field.field_name} className="flex items-center gap-2 pt-5">
                <input
                  id={inputId}
                  type="checkbox"
                  checked={value === true}
                  onChange={(event) => onChange(field.field_name, event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300"
                />
                <span className="font-semibold text-slate-700">{field.label}</span>
              </label>
            );
          }

          return (
            <div key={field.field_name} className="space-y-1">
              <Label htmlFor={inputId} className="font-semibold text-slate-700">{field.label}</Label>
              {field.field_type === 'select' ? (
                <select
                  id={inputId}
                  value={typeof value === 'string' ? value : ''}
                  onChange={(event) => onChange(field.field_name, event.target.value || null)}
                  className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">-- Select --</option>
                  {field.options.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              ) : (
                <Input
                  id={inputId}
                  type={field.field_type === 'number' ? 'number' : 'text'}
                  value={typeof value === 'string' || typeof value === 'number' ? value : ''}
                  onChange={(event) => {
                    if (field.field_type === 'number') {
                      onChange(
                        field.field_name,
                        event.target.value === '' ? null : Number(event.target.value),
                      );
                    } else {
                      onChange(field.field_name, event.target.value);
                    }
                  }}
                  className="h-9 text-xs"
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
