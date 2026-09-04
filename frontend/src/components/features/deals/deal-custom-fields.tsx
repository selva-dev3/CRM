import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { DealCustomFieldDefinition } from '@/lib/api/deals';

type CustomFieldValue = string | number | boolean | null;

function getEmptySelectValue(options: string[]): string {
  let value = '__deal_custom_field_empty__';
  while (options.includes(value)) {
    value += '_';
  }
  return value;
}

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
          const emptySelectValue = getEmptySelectValue(field.options);
          if (field.field_type === 'boolean') {
            return (
              <div key={field.field_name} className="flex items-center gap-2 pt-5">
                <Checkbox
                  id={inputId}
                  checked={value === true}
                  onCheckedChange={(checked) => onChange(field.field_name, checked === true)}
                />
                <Label htmlFor={inputId} className="font-semibold text-slate-700">
                  {field.label}
                </Label>
              </div>
            );
          }

          return (
            <div key={field.field_name} className="space-y-1">
              <Label htmlFor={inputId} className="font-semibold text-slate-700">{field.label}</Label>
              {field.field_type === 'select' ? (
                <Select
                  value={typeof value === 'string' ? value : emptySelectValue}
                  onValueChange={(selectedValue) =>
                    onChange(
                      field.field_name,
                      selectedValue === emptySelectValue ? null : selectedValue,
                    )
                  }
                >
                  <SelectTrigger id={inputId} className="w-full h-9 text-xs">
                    <SelectValue placeholder="-- Select --" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={emptySelectValue}>-- Select --</SelectItem>
                    {field.options.map((option) => (
                      <SelectItem key={option} value={option}>{option}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
