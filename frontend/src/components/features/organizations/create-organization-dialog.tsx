'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { ModalShell } from '@/components/common/modal-shell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { ApiError } from '@/lib/api/client';
import { useCreateOrganizationMutation, type OrganizationCreateResult } from '@/lib/api/organizations';

export const createOrganizationSchema = z.object({
  name: z.string().trim().min(1, 'Organization name is required').max(255, 'Use at most 255 characters'),
  adminName: z.string().trim().max(255),
  adminEmail: z.string().trim(),
}).superRefine((value, context) => {
  if (!value.adminName && !value.adminEmail) return;
  if (!value.adminName) context.addIssue({ code: 'custom', path: ['adminName'], message: 'Admin name is required for an invitation' });
  if (!z.string().email().safeParse(value.adminEmail).success) context.addIssue({ code: 'custom', path: ['adminEmail'], message: 'Enter a valid Admin email address' });
});

export function CreateOrganizationDialog({ onClose, onCreated }: {
  onClose: () => void;
  onCreated: (result: OrganizationCreateResult) => void;
}) {
  const mutation = useCreateOrganizationMutation();
  const form = useForm<z.infer<typeof createOrganizationSchema>>({
    resolver: zodResolver(createOrganizationSchema), defaultValues: { name: '', adminName: '', adminEmail: '' },
  });
  const submit = form.handleSubmit(async (values) => {
    try {
      const result = await mutation.mutateAsync({ name: values.name,
        ...(values.adminEmail ? { initial_admin: { name: values.adminName, email: values.adminEmail } } : {}),
      });
      onCreated(result);
    } catch (error) {
      const fields = { name: 'name', 'initial_admin.name': 'adminName', 'initial_admin.email': 'adminEmail' } as const;
      if (error instanceof ApiError && error.fields) {
        for (const [apiField, formField] of Object.entries(fields)) {
          const message = error.fields[apiField] ?? error.fields[`body.${apiField}`];
          if (typeof message === 'string') form.setError(formField, { message });
        }
      }
      form.setError('root', { message: error instanceof Error ? error.message : 'Unable to create organization' });
    }
  });
  return <ModalShell isOpen title="Create Organization" onClose={() => { if (!mutation.isPending) onClose(); }}>
    <Form {...form}>
      <form className="space-y-4 pt-4" onSubmit={submit} noValidate>
        <FormField control={form.control} name="name" render={({ field }) => <FormItem>
          <FormLabel>Organization Name</FormLabel><FormControl><Input {...field} maxLength={255} autoComplete="organization" /></FormControl><FormMessage />
        </FormItem>} />
        <p className="text-sm text-muted-foreground">Optionally invite the initial Admin. Leave both fields empty to add members later.</p>
        <FormField control={form.control} name="adminName" render={({ field }) => <FormItem>
          <FormLabel>Admin Name (optional)</FormLabel><FormControl><Input {...field} maxLength={255} autoComplete="name" /></FormControl><FormMessage />
        </FormItem>} />
        <FormField control={form.control} name="adminEmail" render={({ field }) => <FormItem>
          <FormLabel>Admin Email (optional)</FormLabel><FormControl><Input {...field} type="email" autoComplete="email" /></FormControl><FormMessage />
        </FormItem>} />
        {form.formState.errors.root && <p role="alert" className="text-sm text-destructive">{form.formState.errors.root.message}</p>}
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" disabled={mutation.isPending} onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={mutation.isPending || form.formState.isSubmitting}>{mutation.isPending ? 'Creating…' : 'Create Organization'}</Button>
        </div>
      </form>
    </Form>
  </ModalShell>;
}
