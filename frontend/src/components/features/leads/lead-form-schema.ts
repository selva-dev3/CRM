import { z } from 'zod';

const optionalText = (max: number, label: string) =>
  z.string().trim().max(max, `${label} must be ${max} characters or fewer.`);

export const leadFormSchema = z.object({
  contact_name: z.string().trim().min(1, 'Contact name is required.').max(255, 'Contact name must be 255 characters or fewer.'),
  email: z.string().trim().min(1, 'Email address is required.').email('Enter a valid email address.').max(255, 'Email must be 255 characters or fewer.'),
  phone: optionalText(50, 'Phone number'),
  title: optionalText(255, 'Lead title'),
  company: z.string().trim().min(1, 'Company name is required.').max(255, 'Company name must be 255 characters or fewer.'),
  website: optionalText(255, 'Website').refine(
    (value) => value === '' || /^https?:\/\/[^\s]+$/i.test(value),
    'Enter a complete URL beginning with http:// or https://.',
  ),
  industry: optionalText(100, 'Industry'),
  company_size: optionalText(50, 'Company size'),
  address: optionalText(255, 'Address'),
  city: optionalText(100, 'City'),
  state: optionalText(100, 'State'),
  country: optionalText(100, 'Country'),
  postal_code: optionalText(20, 'Postal code'),
  source: z.string().trim().min(1, 'Lead source is required.').max(100, 'Lead source must be 100 characters or fewer.'),
  assigned_to: z.string(),
  custom_fields: z.record(z.union([z.string(), z.number(), z.boolean(), z.null()])),
});

export type LeadFormValues = z.infer<typeof leadFormSchema>;

export const LEAD_FORM_DEFAULTS: LeadFormValues = {
  contact_name: '',
  email: '',
  phone: '',
  title: '',
  company: '',
  website: '',
  industry: '',
  company_size: '',
  address: '',
  city: '',
  state: '',
  country: '',
  postal_code: '',
  source: 'Website',
  assigned_to: '',
  custom_fields: {},
};
