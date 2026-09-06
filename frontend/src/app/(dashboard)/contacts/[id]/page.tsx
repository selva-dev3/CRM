'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Mail,
  Phone,
  Building,
  Star,
  Edit,
  Trash2,
  Briefcase,
  Activity,
  FileText,
  MessageSquare,
  PhoneCall,
  MapPin,
  Plus,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { ActionMenu } from '@/components/common/action-menu';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import { PageTabs } from '@/components/common/page-tabs';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import {
  useContactQuery,
  useUpdateContactMutation,
  useContactBillingAddressQuery,
  useUpdateContactBillingAddressMutation,
  useDeleteContactMutation,
  useStarContactMutation,
  useUnstarContactMutation,
  getContactDealsApi,
  getContactActivitiesApi,
  getContactNotesApi,
  addContactNoteApi,
  getContactEmailsApi,
  getContactCallsApi
} from '@/lib/api/contacts';
import { useCompaniesQuery } from '@/lib/api/companies';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { SearchableCompanySelect } from '@/components/common/searchable-company-select';
import { CustomFieldValues } from '@/components/common/custom-field-values';
import { CustomFields } from '@/components/common/custom-fields';
import {
  useEntityCustomFieldsQuery,
  type CustomFieldValue,
} from '@/lib/api/custom-fields';
import type { RelatedRecord } from '@/lib/types';

const activityColumns: DataTableColumn<RelatedRecord>[] = [
  { id: 'type', header: 'Type', cell: (activity) => activity.type || 'Activity' },
  { id: 'description', header: 'Description', cell: (activity) => activity.description || activity.content || 'Contact updated' },
  { id: 'created_at', header: 'Date', cell: (activity) => activity.created_at || 'N/A' },
];

const dealColumns: DataTableColumn<RelatedRecord>[] = [
  { id: 'title', header: 'Deal', cell: (deal) => deal.title || 'Untitled deal' },
  { id: 'stage', header: 'Stage', cell: (deal) => deal.stage || 'N/A' },
  { id: 'amount', header: 'Amount', cell: (deal) => `$${Number(deal.amount || 0).toLocaleString()}` },
];

const noteColumns: DataTableColumn<RelatedRecord>[] = [
  { id: 'content', header: 'Note', cell: (note) => note.content || 'Empty note' },
  { id: 'created_by', header: 'Created By', cell: (note) => note.created_by || 'System User' },
  { id: 'created_at', header: 'Created Date', cell: (note) => note.created_at || 'N/A' },
];

const emailColumns: DataTableColumn<RelatedRecord>[] = [
  { id: 'subject', header: 'Subject', cell: (email) => email.subject || 'No subject' },
  { id: 'to', header: 'Recipient', cell: (email) => Array.isArray(email.to) ? email.to.join(', ') : email.to_email || 'N/A' },
  { id: 'from_email', header: 'Sender', cell: (email) => email.from_email || 'N/A' },
  { id: 'sent_at', header: 'Sent Date', cell: (email) => email.sent_at || 'N/A' },
];

const callColumns: DataTableColumn<RelatedRecord>[] = [
  { id: 'call_type', header: 'Type', cell: (call) => call.call_type || 'Call' },
  { id: 'duration_seconds', header: 'Duration', cell: (call) => `${call.duration_seconds || 0} sec` },
  { id: 'notes', header: 'Notes', cell: (call) => call.notes || 'No notes' },
  { id: 'timestamp', header: 'Date', cell: (call) => call.timestamp || 'N/A' },
];

export default function ContactDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const contactId = params?.id as string;

  const [activeTab, setActiveTab] = useState<'overview' | 'deals' | 'notes' | 'emails' | 'calls'>('overview');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Edit Modal State
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const [formFirstName, setFormFirstName] = useState('');
  const [formLastName, setFormLastName] = useState('');
  const [formName, setFormName] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formPhone, setFormPhone] = useState('');
  const [formCompanyId, setFormCompanyId] = useState('');
  const [formPosition, setFormPosition] = useState('');
  const [formJobTitle, setFormJobTitle] = useState('');
  const [formCustomFields, setFormCustomFields] = useState<
    Record<string, CustomFieldValue>
  >({});
  const [formBillingStreet, setFormBillingStreet] = useState('');
  const [formBillingCity, setFormBillingCity] = useState('');
  const [formBillingState, setFormBillingState] = useState('');
  const [formBillingCountry, setFormBillingCountry] = useState('');
  const [formBillingPostalCode, setFormBillingPostalCode] = useState('');

  // Add Note Form State
  const [newNoteContent, setNewNoteContent] = useState('');

  // Queries
  const { data: contact, isLoading, refetch: refetchContact } = useContactQuery(contactId);
  const {
    data: billingAddress,
    isLoading: isBillingAddressLoading,
    isError: isBillingAddressError,
  } = useContactBillingAddressQuery(contactId);
  const { data: companiesList = [] } = useCompaniesQuery(1, 100);
  const {
    data: customFields = [],
    isLoading: isCustomFieldsLoading,
    isError: isCustomFieldsError,
  } = useEntityCustomFieldsQuery('Contact');

  // Sub-resource queries
  const { data: deals = [], isError: isDealsError } = useQuery({
    queryKey: ['contact-deals', contactId],
    queryFn: () => getContactDealsApi(contactId),
    enabled: !!contactId,
  });

  const { data: activities = [], isError: isActivitiesError } = useQuery({
    queryKey: ['contact-activities', contactId],
    queryFn: () => getContactActivitiesApi(contactId),
    enabled: !!contactId,
  });

  const { data: notes = [], isError: isNotesError, refetch: refetchNotes } = useQuery({
    queryKey: ['contact-notes', contactId],
    queryFn: () => getContactNotesApi(contactId),
    enabled: !!contactId,
  });

  const { data: emails = [], isError: isEmailsError } = useQuery({
    queryKey: ['contact-emails', contactId],
    queryFn: () => getContactEmailsApi(contactId),
    enabled: !!contactId,
  });

  const { data: calls = [], isError: isCallsError } = useQuery({
    queryKey: ['contact-calls', contactId],
    queryFn: () => getContactCallsApi(contactId),
    enabled: !!contactId,
  });

  // Mutations
  const updateContactMutation = useUpdateContactMutation();
  const updateBillingAddressMutation = useUpdateContactBillingAddressMutation();
  const deleteContactMutation = useDeleteContactMutation();
  const starContactMutation = useStarContactMutation();
  const unstarContactMutation = useUnstarContactMutation();

  const addNoteMutation = useMutation({
    mutationFn: (content: string) => addContactNoteApi({ id: contactId, content }),
    onSuccess: () => {
      setSuccessMessage('Note added successfully.');
      setNewNoteContent('');
      refetchNotes();
      queryClient.invalidateQueries({ queryKey: ['contact-notes', contactId] });
    },
    onError: () => {
      setErrorMessage('Failed to add note.');
    },
  });

  const openEditModal = () => {
    if (contact) {
      const parts = contact.name ? contact.name.split(' ') : [];
      setFormFirstName(parts[0] || '');
      setFormLastName(parts.slice(1).join(' ') || '');
      setFormName(contact.name || '');
      setFormEmail(contact.email || '');
      setFormPhone(contact.phone || '');
      setFormCompanyId(contact.company_id || '');
      setFormPosition(contact.position || '');
      setFormJobTitle(contact.position || '');
      setFormCustomFields(contact.custom_fields ?? {});
      setFormBillingStreet(billingAddress?.street || '');
      setFormBillingCity(billingAddress?.city || '');
      setFormBillingState(billingAddress?.state || '');
      setFormBillingCountry(billingAddress?.country || '');
      setFormBillingPostalCode(billingAddress?.postal_code || '');
      setIsEditModalOpen(true);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setErrorMessage(null);
      if (!formBillingStreet.trim() || !formBillingCountry.trim()) {
        setErrorMessage('Billing street and country are required for automatic invoices.');
        return;
      }
      const displayName = formName || `${formFirstName} ${formLastName}`.trim() || 'Contact';
      await updateContactMutation.mutateAsync({
        id: contactId,
        data: {
          first_name: formFirstName || undefined,
          last_name: formLastName || undefined,
          name: displayName,
          email: formEmail,
          phone: formPhone || undefined,
          company_id: formCompanyId || undefined,
          position: formPosition || undefined,
          job_title: formJobTitle || formPosition || undefined,
          custom_fields: formCustomFields,
        },
      });
      await updateBillingAddressMutation.mutateAsync({
        id: contactId,
        data: {
          street: formBillingStreet.trim(),
          city: formBillingCity.trim() || undefined,
          state: formBillingState.trim() || undefined,
          country: formBillingCountry.trim(),
          postal_code: formBillingPostalCode.trim() || undefined,
        },
      });
      setSuccessMessage('Contact updated successfully.');
      setIsEditModalOpen(false);
      refetchContact();
    } catch {
      setErrorMessage('Failed to update contact.');
    }
  };

  const handleToggleStar = async () => {
    if (!contact) return;
    try {
      setErrorMessage(null);
      if (contact.is_starred) {
        await unstarContactMutation.mutateAsync(contactId);
        setSuccessMessage('Contact unstarred.');
      } else {
        await starContactMutation.mutateAsync(contactId);
        setSuccessMessage('Contact starred.');
      }
      refetchContact();
    } catch {
      setErrorMessage('Failed to update star status.');
    }
  };

  const handleConfirmDelete = async () => {
    try {
      setErrorMessage(null);
      await deleteContactMutation.mutateAsync(contactId);
      router.push('/contacts');
    } catch {
      setErrorMessage('Failed to delete contact.');
      setIsDeleteModalOpen(false);
    }
  };

  const companyName = contact?.company_id
    ? companiesList.find((c) => c.id === contact.company_id)?.name || 'Enterprise Partner'
    : 'Primary Organization';
  const hasRelationshipError =
    isDealsError || isActivitiesError || isNotesError || isEmailsError || isCallsError;

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center text-slate-500 text-sm font-semibold">
        Loading contact details...
      </div>
    );
  }

  if (!contact) {
    return (
      <div className="p-8 space-y-4">
        <Link href="/contacts" className="text-blue-600 text-xs font-semibold hover:underline flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Contacts</span>
        </Link>
        <div className="p-6 bg-slate-50 border border-slate-200 rounded-2xl text-slate-700 text-sm">
          Contact profile not found or has been removed.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Actions Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <Link href="/contacts" className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-blue-600 transition">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Contact Directory</span>
        </Link>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <Button
            size="sm"
            variant="outline"
            onClick={handleToggleStar}
            disabled={starContactMutation.isPending || unstarContactMutation.isPending}
            className={`border-slate-300 font-semibold text-xs gap-1.5 cursor-pointer ${
              contact.is_starred ? 'bg-amber-50 text-amber-600 border-amber-200 hover:bg-amber-100' : 'text-slate-700 hover:bg-slate-50'
            }`}
          >
            <Star className={`w-4 h-4 ${contact.is_starred ? 'fill-amber-400 text-amber-500' : 'text-slate-400'}`} />
            <span>{contact.is_starred ? 'Unstar Contact' : 'Star Contact'}</span>
          </Button>

          <ActionMenu
            label="More"
            className="h-8 text-xs font-semibold"
            actions={[
              {
                label: 'Edit profile',
                icon: <Edit className="w-4 h-4 text-blue-600" />,
                onSelect: openEditModal,
              },
              {
                label: 'Delete contact',
                icon: <Trash2 className="w-4 h-4" />,
                variant: 'destructive',
                onSelect: () => setIsDeleteModalOpen(true),
              },
            ]}
          />
        </div>
      </div>

      {/* Feedback Banners */}
      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-sm font-medium flex items-center gap-2 animate-in fade-in-50">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-sm font-medium flex items-center gap-2 animate-in fade-in-50">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Contact Main Info Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600 text-white font-bold text-xl shadow-md shrink-0">
            {contact.name ? contact.name.charAt(0).toUpperCase() : 'C'}
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold text-slate-900">{contact.name}</h1>
              {(contact.is_starred || contact.status) && (
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-900 border border-amber-300 flex items-center gap-1">
                  <Star className="w-3 h-3 fill-amber-400 text-amber-600" />
                  <span>{contact.status || 'Star Contact'}</span>
                </span>
              )}
            </div>
            <p className="text-xs font-semibold text-slate-500 mt-0.5">{contact.position || 'Representative'}</p>
            <div className="flex items-center gap-4 mt-3 text-xs text-slate-600 flex-wrap">
              <div className="flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5 text-slate-400" />
                <span className="font-semibold">{contact.email}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Phone className="w-3.5 h-3.5 text-slate-400" />
                <span>{contact.phone || 'N/A'}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Building className="w-3.5 h-3.5 text-slate-400" />
                <span className="font-semibold text-blue-700">{companyName}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
        <div className="flex items-center gap-2 mb-4">
          <MapPin className="w-4 h-4 text-blue-600" />
          <h2 className="text-sm font-bold text-slate-900">Billing Address</h2>
        </div>
        {isBillingAddressLoading ? (
          <p className="text-xs text-slate-500">Loading billing address...</p>
        ) : isBillingAddressError ? (
          <p className="text-xs text-rose-700">Billing address could not be loaded. Retry the page to try again.</p>
        ) : billingAddress?.street && billingAddress.country ? (
          <div className="grid grid-cols-1 gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <p className="font-semibold text-slate-500">Street</p>
              <p className="mt-1 text-slate-900">{billingAddress.street}</p>
            </div>
            <div>
              <p className="font-semibold text-slate-500">City</p>
              <p className="mt-1 text-slate-900">{billingAddress.city || 'N/A'}</p>
            </div>
            <div>
              <p className="font-semibold text-slate-500">State</p>
              <p className="mt-1 text-slate-900">{billingAddress.state || 'N/A'}</p>
            </div>
            <div>
              <p className="font-semibold text-slate-500">Country / Postal Code</p>
              <p className="mt-1 text-slate-900">
                {billingAddress.country}{billingAddress.postal_code ? ` / ${billingAddress.postal_code}` : ''}
              </p>
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-500">Billing address not added.</p>
        )}
      </div>

      <CustomFieldValues fields={customFields} values={contact.custom_fields ?? {}} />

      <PageTabs
        value={activeTab}
        onValueChange={setActiveTab}
        tabs={[
          { value: 'overview', icon: <Activity className="size-4" />, label: `Overview & Timeline (${activities.length})` },
          { value: 'deals', icon: <Briefcase className="size-4" />, label: `Deals (${deals.length})` },
          { value: 'notes', icon: <FileText className="size-4" />, label: `Notes (${notes.length})` },
          { value: 'emails', icon: <MessageSquare className="size-4" />, label: `Emails (${emails.length})` },
          { value: 'calls', icon: <PhoneCall className="size-4" />, label: `Call Logs (${calls.length})` },
        ]}
        listClassName="border-b border-slate-200"
      />

      {hasRelationshipError && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs font-medium text-amber-900">
          Some related contact records could not be loaded. Retry the page to try again.
        </div>
      )}

      {/* TAB CONTENT: Overview */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Activity Timeline</h2>
          <DataTable
            columns={activityColumns}
            data={activities}
            getRowKey={(activity) => activity.id}
            emptyTitle="No recent activity"
            emptyDescription="No recent activity recorded for this contact."
          />
        </div>
      )}

      {/* TAB CONTENT: Deals */}
      {activeTab === 'deals' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Linked Sales Deals</h2>
          <DataTable
            columns={dealColumns}
            data={deals}
            getRowKey={(deal) => deal.id}
            emptyTitle="No linked deals"
            emptyDescription="No active sales pipeline deals are associated with this contact."
          />
        </div>
      )}

      {/* TAB CONTENT: Notes */}
      {activeTab === 'notes' && (
        <div className="space-y-4">
          <div className="p-4 bg-white rounded-2xl border border-slate-200 space-y-3">
            <Label className="font-semibold text-slate-700 text-xs">Add New Note</Label>
            <Input
              type="text"
              placeholder="Type note details for this contact profile..."
              value={newNoteContent}
              onChange={(e) => setNewNoteContent(e.target.value)}
              className="h-9 text-xs"
            />
            <div className="flex justify-end">
              <Button
                size="sm"
                onClick={() => addNoteMutation.mutate(newNoteContent)}
                disabled={!newNoteContent.trim() || addNoteMutation.isPending}
                className="bg-blue-600 text-white font-semibold text-xs gap-1 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>Add Note</span>
              </Button>
            </div>
          </div>

          <h2 className="text-sm font-bold text-slate-900 pt-2">Saved Notes</h2>
          <DataTable
            columns={noteColumns}
            data={notes}
            getRowKey={(note) => note.id}
            emptyTitle="No saved notes"
            emptyDescription="No notes logged yet. Add your first note above."
          />
        </div>
      )}

      {/* TAB CONTENT: Emails */}
      {activeTab === 'emails' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Email History</h2>
          <DataTable
            columns={emailColumns}
            data={emails}
            getRowKey={(email) => email.id}
            emptyTitle="No email messages"
            emptyDescription="No email messages have been sent to this contact."
            expandableRow={(email) => (
              <div className="space-y-1 text-xs text-slate-600">
                <p>{email.body_text || email.body || 'No preview body.'}</p>
              </div>
            )}
          />
        </div>
      )}

      {/* TAB CONTENT: Calls */}
      {activeTab === 'calls' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Telephony Call Logs</h2>
          <DataTable
            columns={callColumns}
            data={calls}
            getRowKey={(call) => call.id}
            emptyTitle="No call logs"
            emptyDescription="No call logs have been recorded for this contact."
          />
        </div>
      )}

      {/* EDIT MODAL */}
      {isEditModalOpen && (
        <ModalShell
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          size="md"
          title={
            <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
              <Edit className="w-5 h-5 text-blue-600" />
              <span>Edit Contact Details</span>
            </h3>
          }
        >
          <form onSubmit={handleEditSubmit} className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">First Name</Label>
                <Input
                  type="text"
                  value={formFirstName}
                  onChange={(e) => setFormFirstName(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Last Name</Label>
                <Input
                  type="text"
                  value={formLastName}
                  onChange={(e) => setFormLastName(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Full Name</Label>
              <Input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Email Address</Label>
                <Input
                  type="text"
                  value={formEmail}
                  onChange={(e) => setFormEmail(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Phone Number</Label>
                <Input
                  type="text"
                  value={formPhone}
                  onChange={(e) => setFormPhone(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Company</Label>
              <SearchableCompanySelect
                value={formCompanyId}
                onChange={setFormCompanyId}
                companies={companiesList}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Position</Label>
                <Input
                  type="text"
                  value={formPosition}
                  onChange={(e) => setFormPosition(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Job Title</Label>
                <Input
                  type="text"
                  value={formJobTitle}
                  onChange={(e) => setFormJobTitle(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
            </div>

            <div className="space-y-2 rounded-lg border border-slate-200 p-3">
              <div>
                <h4 className="font-semibold text-slate-800">Billing Address</h4>
                <p className="text-[11px] text-slate-500">Street and country are required before an invoice can be created.</p>
              </div>
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Street *</Label>
                <Input
                  type="text"
                  value={formBillingStreet}
                  onChange={(e) => setFormBillingStreet(e.target.value)}
                  className="h-9 text-xs"
                  required
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">City</Label>
                  <Input type="text" value={formBillingCity} onChange={(e) => setFormBillingCity(e.target.value)} className="h-9 text-xs" />
                </div>
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">State</Label>
                  <Input type="text" value={formBillingState} onChange={(e) => setFormBillingState(e.target.value)} className="h-9 text-xs" />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Country *</Label>
                  <Input type="text" value={formBillingCountry} onChange={(e) => setFormBillingCountry(e.target.value)} className="h-9 text-xs" required />
                </div>
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Postal Code</Label>
                  <Input type="text" value={formBillingPostalCode} onChange={(e) => setFormBillingPostalCode(e.target.value)} className="h-9 text-xs" />
                </div>
              </div>
            </div>

            <CustomFields
              fields={customFields}
              values={formCustomFields}
              onChange={(fieldName, value) => {
                setFormCustomFields((current) => ({ ...current, [fieldName]: value }));
              }}
              isLoading={isCustomFieldsLoading}
              isError={isCustomFieldsError}
              idPrefix="contact-detail-edit"
            />

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsEditModalOpen(false)} className="cursor-pointer">
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={updateContactMutation.isPending || updateBillingAddressMutation.isPending} className="bg-blue-600 text-white font-semibold cursor-pointer">
                {updateContactMutation.isPending || updateBillingAddressMutation.isPending ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* CONFIRM DELETE MODAL */}
      <ConfirmModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onConfirm={handleConfirmDelete}
        title="Delete Contact Profile"
        description="This action cannot be undone."
        confirmText="Delete Contact"
        variant="danger"
        isLoading={deleteContactMutation.isPending}
        message={
          <p>
            Are you sure you want to delete contact <strong className="text-slate-900">{contact.name}</strong> ({contact.email})?
          </p>
        }
      />
    </div>
  );
}
