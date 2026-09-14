'use client';

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, Building2, Check, ChevronLeft, ChevronRight, Loader2, MapPin, Pencil, Plus, UserRound } from 'lucide-react';
import { useForm, useWatch, type FieldErrors, type FieldPath } from 'react-hook-form';

import { ConfirmModal } from '@/components/common/confirm-modal';
import { CustomFields } from '@/components/common/custom-fields';
import { CompanyNameSelect } from '@/components/common/company-name-select';
import { ModalShell } from '@/components/common/modal-shell';
import { UserSelect } from '@/components/common/user-select';
import { Alert, AlertDescription, Button, Input, Label } from '@/components/ui';
import { useHasPermission } from '@/hooks/use-has-permission';
import { ApiError } from '@/lib/api/client';
import { useEntityCustomFieldsQuery } from '@/lib/api/custom-fields';
import {
  checkLeadDuplicateApi,
  type CreateLeadPayload,
  type Lead,
  useCreateLeadMutation,
  useUpdateLeadMutation,
} from '@/lib/api/leads';
import { useCurrentOrganizationQuery } from '@/lib/api/organizations';
import { PERMISSIONS } from '@/lib/permissions';
import { cn } from '@/lib/utils';
import { LEAD_FORM_DEFAULTS, leadFormSchema, type LeadFormValues } from './lead-form-schema';

const STEPS = [
  { id: 0, label: 'Lead details', shortLabel: 'Details', icon: UserRound },
  { id: 1, label: 'Company & location', shortLabel: 'Company', icon: Building2 },
  { id: 2, label: 'Ownership & review', shortLabel: 'Review', icon: Check },
] as const;

const STEP_FIELDS: readonly (readonly FieldPath<LeadFormValues>[])[] = [
  ['contact_name', 'email', 'phone', 'title'],
  ['company', 'website', 'industry', 'company_size', 'address', 'city', 'state', 'country', 'postal_code'],
  ['source', 'assigned_to', 'custom_fields'],
];

const SOURCE_OPTIONS = ['Website', 'LinkedIn', 'Referral', 'Cold Call', 'Event', 'Partner'];
const COMPANY_SIZE_OPTIONS = ['1-10', '11-50', '51-200', '201-500', '500+', '501-1000', '1000+'];

function valuesForLead(lead?: Lead | null): LeadFormValues {
  if (!lead) return { ...LEAD_FORM_DEFAULTS, custom_fields: {} };
  return {
    contact_name: lead.contact_name ?? '',
    email: lead.email ?? '',
    phone: lead.phone ?? '',
    title: lead.title ?? '',
    company: lead.company ?? '',
    website: lead.website ?? '',
    industry: lead.industry ?? '',
    company_size: lead.company_size ?? '',
    address: lead.address ?? '',
    city: lead.city ?? '',
    state: lead.state ?? '',
    country: lead.country ?? '',
    postal_code: lead.postal_code ?? '',
    source: lead.source || 'Website',
    assigned_to: lead.assigned_to ?? '',
    custom_fields: lead.custom_fields ?? {},
  };
}

function optional(value: string): string | undefined {
  return value || undefined;
}

interface LeadFormDialogProps {
  isOpen: boolean;
  onClose: () => void;
  lead?: Lead | null;
  onSaved: (lead: Lead, mode: 'created' | 'updated') => void;
}

export function LeadFormDialog({ isOpen, onClose, lead, onSaved }: LeadFormDialogProps) {
  const isEditing = Boolean(lead);
  const [step, setStep] = useState(0);
  const [serverError, setServerError] = useState<string | null>(null);
  const [showDiscardConfirmation, setShowDiscardConfirmation] = useState(false);
  const [debouncedEmail, setDebouncedEmail] = useState('');
  const contactNameRef = useRef<HTMLInputElement | null>(null);
  const { hasPermission } = useHasPermission();
  const canAssign = !isEditing && hasPermission(PERMISSIONS.LEADS.ASSIGN);
  const canReadCompanies = hasPermission(PERMISSIONS.COMPANIES.READ);
  const canCheckDuplicates = hasPermission(PERMISSIONS.LEADS.READ);
  const createLead = useCreateLeadMutation();
  const updateLead = useUpdateLeadMutation();
  const isSaving = createLead.isPending || updateLead.isPending;
  const organization = useCurrentOrganizationQuery();
  const customFields = useEntityCustomFieldsQuery('Lead', isOpen);

  const form = useForm<LeadFormValues>({
    resolver: zodResolver(leadFormSchema),
    mode: 'onBlur',
    defaultValues: valuesForLead(lead),
  });
  const { formState: { errors, isDirty }, register, setError, setValue, control } = form;
  const email = useWatch({ control, name: 'email' });
  const phone = useWatch({ control, name: 'phone' });
  const companyName = useWatch({ control, name: 'company' });
  const assignedTo = useWatch({ control, name: 'assigned_to' });
  const formCustomFields = useWatch({ control, name: 'custom_fields' }) ?? {};
  const formValues = useWatch({ control });

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedEmail(email.trim().toLowerCase()), 350);
    return () => window.clearTimeout(timer);
  }, [email]);

  const duplicateCheck = useQuery({
    queryKey: ['lead-duplicate-check', debouncedEmail, phone.trim()],
    queryFn: () => checkLeadDuplicateApi(debouncedEmail, optional(phone.trim())),
    enabled: isOpen && !isEditing && canCheckDuplicates && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(debouncedEmail),
    staleTime: 30_000,
    retry: false,
  });

  const stepHasError = (stepIndex: number) => STEP_FIELDS[stepIndex].some((name) => {
    const rootName = String(name).split('.')[0] as keyof LeadFormValues;
    return Boolean(errors[rootName]);
  });

  const requestClose = () => {
    if (isSaving) return;
    if (isDirty) {
      setShowDiscardConfirmation(true);
      return;
    }
    onClose();
  };

  const goForward = async (target = step + 1) => {
    const fieldsToValidate = STEP_FIELDS.slice(0, target).flat();
    const valid = await form.trigger(fieldsToValidate, { shouldFocus: true });
    if (valid) setStep(Math.min(target, STEPS.length - 1));
  };

  const jumpToStep = async (target: number) => {
    if (target <= step) {
      setStep(target);
      return;
    }
    await goForward(target);
  };

  const focusFirstInvalidStep = (validationErrors: FieldErrors<LeadFormValues>) => {
    const invalidStep = STEP_FIELDS.findIndex((fields) => fields.some((name) => {
      const rootName = String(name).split('.')[0] as keyof LeadFormValues;
      return Boolean(validationErrors[rootName]);
    }));
    if (invalidStep >= 0) setStep(invalidStep);
  };

  const submit = form.handleSubmit(async (values) => {
    setServerError(null);
    const payload: CreateLeadPayload = {
      contact_name: values.contact_name,
      email: values.email,
      phone: optional(values.phone),
      title: values.title || `${values.contact_name} Opportunity`,
      company: values.company,
      website: optional(values.website),
      industry: optional(values.industry),
      company_size: optional(values.company_size),
      address: optional(values.address),
      city: optional(values.city),
      state: optional(values.state),
      country: optional(values.country),
      postal_code: optional(values.postal_code),
      source: values.source,
      custom_fields: values.custom_fields,
      ...(isEditing ? {} : {
        status: 'New',
        is_archived: false,
        assigned_to: canAssign ? optional(values.assigned_to) : undefined,
      }),
    };

    try {
      const saved = lead
        ? await updateLead.mutateAsync({ id: lead.id, payload })
        : await createLead.mutateAsync(payload);
      form.reset(values);
      onSaved(saved, lead ? 'updated' : 'created');
    } catch (error) {
      if (error instanceof ApiError && error.fields) {
        let firstServerErrorStep = -1;
        for (const [field, message] of Object.entries(error.fields)) {
          if (field in LEAD_FORM_DEFAULTS) {
            if (firstServerErrorStep < 0) {
              firstServerErrorStep = STEP_FIELDS.findIndex((fields) => fields.some((name) => String(name).split('.')[0] === field));
            }
            setError(field as FieldPath<LeadFormValues>, {
              type: 'server',
              message: typeof message === 'string' ? message : 'This value is invalid.',
            });
          }
        }
        if (firstServerErrorStep >= 0) setStep(firstServerErrorStep);
      }
      setServerError(error instanceof Error && error.message
        ? error.message
        : `The lead could not be ${lead ? 'updated' : 'created'}. Please try again.`);
    }
  }, focusFirstInvalidStep);

  const contactRegistration = register('contact_name');
  const reviewRows = useMemo(() => [
    ['Contact', formValues.contact_name || 'Not provided'],
    ['Email', formValues.email || 'Not provided'],
    ['Company', formValues.company || 'Not provided'],
    ['Source', formValues.source || 'Not provided'],
  ], [formValues.company, formValues.contact_name, formValues.email, formValues.source]);

  const fieldClass = 'h-10 border-slate-300 bg-white text-sm text-slate-950 placeholder:text-slate-400 focus-visible:border-indigo-500 focus-visible:ring-indigo-500/20';

  const fieldError = (name: keyof LeadFormValues) => {
    const message = errors[name]?.message;
    return typeof message === 'string' ? <p id={`lead-${name}-error`} className="text-xs font-medium text-rose-600">{message}</p> : null;
  };

  return (
    <>
      <ModalShell
        isOpen={isOpen}
        onClose={requestClose}
        size="3xl"
        ariaLabel={isEditing ? 'Edit sales lead' : 'Create new sales lead'}
        initialFocusRef={contactNameRef}
        contentClassName="h-[min(760px,calc(100dvh-1rem))] max-h-[calc(100dvh-1rem)] overflow-hidden p-0 sm:h-[min(760px,calc(100dvh-2rem))] sm:p-0 max-sm:max-w-none max-sm:rounded-none [&_[data-slot=dialog-header]]:pr-5 sm:[&_[data-slot=dialog-header]]:pr-6"
        bodyClassName="flex min-h-0 flex-1 flex-col overflow-hidden pt-0"
        title={
          <div className="flex items-center gap-3 px-5 py-4 sm:px-6">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm">
              {isEditing ? <Pencil className="size-4" /> : <Plus className="size-5" />}
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-lg font-bold text-slate-950 sm:text-xl">{isEditing ? 'Edit sales lead' : 'Create new sales lead'}</h2>
              <p className="text-xs text-slate-600 sm:text-sm">{isEditing ? `Update ${lead?.contact_name}` : 'Add the essentials now; enrich the record later.'}</p>
            </div>
          </div>
        }
      >
        <form onSubmit={submit} noValidate className="flex min-h-0 flex-1 flex-col">
          <nav aria-label="Lead form progress" className="shrink-0 border-b border-slate-200 bg-slate-50 px-4 py-3 sm:px-6">
            <ol className="grid grid-cols-3 gap-2">
              {STEPS.map((item) => {
                const Icon = item.icon;
                const active = step === item.id;
                const hasError = stepHasError(item.id);
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      aria-current={active ? 'step' : undefined}
                      onClick={() => void jumpToStep(item.id)}
                      disabled={isSaving}
                      className={cn(
                        'flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-xs font-semibold transition-colors sm:px-3 sm:text-sm',
                        active ? 'bg-white text-indigo-700 shadow-sm ring-1 ring-slate-200' : 'text-slate-500 hover:bg-white hover:text-slate-800',
                        hasError && 'text-rose-700 ring-1 ring-rose-200',
                      )}
                    >
                      <span className={cn('flex size-7 shrink-0 items-center justify-center rounded-full bg-slate-200', active && 'bg-indigo-100', hasError && 'bg-rose-100')}>
                        <Icon className="size-3.5" />
                      </span>
                      <span className="hidden sm:inline">{item.label}</span>
                      <span className="sm:hidden">{item.shortLabel}</span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </nav>

          <fieldset disabled={isSaving} className="min-h-0 flex-1 overflow-y-auto px-5 py-5 disabled:opacity-70 sm:px-6 sm:py-6">
            {serverError && (
              <Alert variant="destructive" className="mb-5" role="alert">
                <AlertCircle className="size-4" />
                <AlertDescription>{serverError}</AlertDescription>
              </Alert>
            )}

            {step === 0 && (
              <section aria-labelledby="lead-details-heading" className="space-y-5">
                <div>
                  <h3 id="lead-details-heading" className="text-base font-bold text-slate-950">Who is this lead?</h3>
                  <p className="mt-1 text-sm text-slate-500">Fields marked with * are required.</p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="lead-contact-name">Contact name *</Label>
                    <Input id="lead-contact-name" autoComplete="name" placeholder="e.g. John Doe" aria-invalid={Boolean(errors.contact_name)} aria-describedby={errors.contact_name ? 'lead-contact_name-error' : undefined} {...contactRegistration} ref={(node) => { contactRegistration.ref(node); contactNameRef.current = node; }} className={fieldClass} />
                    {fieldError('contact_name')}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="lead-email">Email address *</Label>
                    <Input id="lead-email" type="email" autoComplete="email" placeholder="john@acme.com" aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? 'lead-email-error' : undefined} {...register('email')} className={fieldClass} />
                    {fieldError('email')}
                    {!isEditing && duplicateCheck.isFetching && <p className="flex items-center gap-1.5 text-xs text-slate-500"><Loader2 className="size-3 animate-spin" />Checking for an existing lead…</p>}
                    {!isEditing && duplicateCheck.data?.is_duplicate && duplicateCheck.data.matched_lead_id && (
                      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                        A lead with this email already exists. <Link className="font-bold underline" href={`/leads/${duplicateCheck.data.matched_lead_id}`} target="_blank" rel="noreferrer">Review existing lead</Link>
                      </div>
                    )}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="lead-phone">Phone number</Label>
                    <Input id="lead-phone" type="tel" autoComplete="tel" placeholder="+1 (555) 000-0000" aria-invalid={Boolean(errors.phone)} aria-describedby={errors.phone ? 'lead-phone-error' : undefined} {...register('phone')} className={fieldClass} />
                    {fieldError('phone')}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="lead-title">Lead title</Label>
                    <Input id="lead-title" placeholder="e.g. Enterprise Cloud Deal" aria-invalid={Boolean(errors.title)} aria-describedby={errors.title ? 'lead-title-error' : 'lead-title-help'} {...register('title')} className={fieldClass} />
                    <p id="lead-title-help" className="text-xs text-slate-500">If left blank, a title is generated from the contact name.</p>
                    {fieldError('title')}
                  </div>
                </div>
              </section>
            )}

            {step === 1 && (
              <section aria-labelledby="company-location-heading" className="space-y-6">
                <div>
                  <h3 id="company-location-heading" className="text-base font-bold text-slate-950">Company and location</h3>
                  <p className="mt-1 text-sm text-slate-500">Choose an existing company name or enter a new one.</p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="lead-company">Company name *</Label>
                    <CompanyNameSelect
                      id="lead-company"
                      value={companyName}
                      onChange={(value) => setValue('company', value, { shouldDirty: true, shouldValidate: true })}
                      enabled={isOpen && canReadCompanies}
                      disabled={isSaving}
                      aria-invalid={Boolean(errors.company)}
                      aria-describedby={errors.company ? 'lead-company-error' : 'lead-company-help'}
                      className={fieldClass}
                    />
                    <p id="lead-company-help" className="text-xs text-slate-500">The lead stores the company name; selecting a suggestion does not create a new company record.</p>
                    {fieldError('company')}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="lead-website">Website</Label>
                    <Input id="lead-website" type="url" autoComplete="url" placeholder="https://company.com" aria-invalid={Boolean(errors.website)} aria-describedby={errors.website ? 'lead-website-error' : undefined} {...register('website')} className={fieldClass} />
                    {fieldError('website')}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="lead-industry">Industry</Label>
                    <Input id="lead-industry" placeholder="e.g. Software" aria-invalid={Boolean(errors.industry)} aria-describedby={errors.industry ? 'lead-industry-error' : undefined} {...register('industry')} className={fieldClass} />
                    {fieldError('industry')}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="lead-company-size">Company size</Label>
                    <select id="lead-company-size" {...register('company_size')} className={cn(fieldClass, 'w-full rounded-md border px-3')}>
                      <option value="">Select company size</option>
                      {COMPANY_SIZE_OPTIONS.map((size) => <option key={size} value={size}>{size} employees</option>)}
                      {formValues.company_size && !COMPANY_SIZE_OPTIONS.includes(formValues.company_size) && <option value={formValues.company_size}>{formValues.company_size} (existing)</option>}
                    </select>
                  </div>
                </div>
                <div className="border-t border-slate-200 pt-5">
                  <div className="mb-4 flex items-center gap-2"><MapPin className="size-4 text-indigo-600" /><h4 className="font-semibold text-slate-900">Address</h4><span className="text-xs text-slate-500">Optional</span></div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5 sm:col-span-2"><Label htmlFor="lead-address">Street address</Label><Input id="lead-address" autoComplete="street-address" placeholder="Street, suite, or building" {...register('address')} className={fieldClass} />{fieldError('address')}</div>
                    <div className="space-y-1.5"><Label htmlFor="lead-city">City</Label><Input id="lead-city" autoComplete="address-level2" {...register('city')} className={fieldClass} />{fieldError('city')}</div>
                    <div className="space-y-1.5"><Label htmlFor="lead-state">State / region</Label><Input id="lead-state" autoComplete="address-level1" {...register('state')} className={fieldClass} />{fieldError('state')}</div>
                    <div className="space-y-1.5"><Label htmlFor="lead-country">Country</Label><Input id="lead-country" autoComplete="country-name" {...register('country')} className={fieldClass} />{fieldError('country')}</div>
                    <div className="space-y-1.5"><Label htmlFor="lead-postal-code">Postal code</Label><Input id="lead-postal-code" autoComplete="postal-code" {...register('postal_code')} className={fieldClass} />{fieldError('postal_code')}</div>
                  </div>
                </div>
              </section>
            )}

            {step === 2 && (
              <section aria-labelledby="ownership-review-heading" className="space-y-6">
                <div>
                  <h3 id="ownership-review-heading" className="text-base font-bold text-slate-950">Ownership and review</h3>
                  <p className="mt-1 text-sm text-slate-500">Confirm how this lead enters your CRM.</p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="lead-source">Lead source</Label>
                    <select id="lead-source" {...register('source')} className={cn(fieldClass, 'w-full rounded-md border px-3')}>{SOURCE_OPTIONS.map((source) => <option key={source}>{source}</option>)}{formValues.source && !SOURCE_OPTIONS.includes(formValues.source) && <option value={formValues.source}>{formValues.source} (existing)</option>}</select>
                    {fieldError('source')}
                  </div>
                  {canAssign && <div className="space-y-1.5"><Label>Assign to</Label><UserSelect value={assignedTo} onChange={(value) => setValue('assigned_to', value, { shouldDirty: true })} disabled={isSaving} ariaLabel="Assign lead to user" /><p className="text-xs text-slate-500">Optional. Leave empty to keep the lead unassigned.</p></div>}
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Status</p><p className="mt-1 font-bold text-slate-900">{lead?.status || 'New'}</p><p className="mt-1 text-xs text-slate-500">Change status later through lifecycle actions.</p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Organization</p><p className="mt-1 font-bold text-slate-900">{organization.isLoading ? 'Loading…' : organization.data?.name || 'Current organization'}</p><p className="mt-1 text-xs text-slate-500">Set securely from your current session.</p>
                  </div>
                </div>
                <CustomFields
                  fields={customFields.data ?? []}
                  values={formCustomFields}
                  onChange={(name, value) => setValue(
                    'custom_fields',
                    { ...formCustomFields, [name]: value },
                    { shouldDirty: true },
                  )}
                  isLoading={customFields.isLoading}
                  isError={customFields.isError}
                  idPrefix="lead-form"
                />
                <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-4">
                  <h4 className="text-sm font-bold text-slate-950">Review</h4>
                  <dl className="mt-3 grid gap-3 sm:grid-cols-2">{reviewRows.map(([label, value]) => <div key={label}><dt className="text-xs font-medium text-slate-500">{label}</dt><dd className="mt-0.5 break-words text-sm font-semibold text-slate-900">{value}</dd></div>)}</dl>
                </div>
              </section>
            )}
          </fieldset>

          <footer className="shrink-0 border-t border-slate-200 bg-white px-4 py-3 sm:px-6">
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
              <Button type="button" variant="outline" onClick={requestClose} disabled={isSaving}>Cancel</Button>
              <div className="flex gap-2">
                {step > 0 && <Button type="button" variant="outline" onClick={() => setStep((current) => current - 1)} disabled={isSaving}><ChevronLeft className="size-4" />Previous</Button>}
                {step < STEPS.length - 1 ? (
                  <Button type="button" onClick={() => void goForward()} disabled={isSaving} className="ml-auto bg-indigo-600 hover:bg-indigo-700">Continue<ChevronRight className="size-4" /></Button>
                ) : (
                  <Button type="submit" disabled={isSaving} className="ml-auto min-w-32 bg-indigo-600 hover:bg-indigo-700">{isSaving ? <><Loader2 className="size-4 animate-spin" />Saving…</> : isEditing ? 'Save changes' : 'Create lead'}</Button>
                )}
              </div>
            </div>
          </footer>
        </form>
      </ModalShell>

      <ConfirmModal
        isOpen={showDiscardConfirmation}
        onClose={() => setShowDiscardConfirmation(false)}
        onConfirm={() => { setShowDiscardConfirmation(false); form.reset(valuesForLead(lead)); onClose(); }}
        title="Discard unsaved changes?"
        description="The information entered in this form will be lost."
        confirmText="Discard changes"
        cancelText="Keep editing"
        variant="warning"
      />
    </>
  );
}
