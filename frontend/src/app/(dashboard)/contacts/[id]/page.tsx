'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  User,
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
  Plus,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  Search,
  Check
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import {
  useContactQuery,
  useUpdateContactMutation,
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

function SearchableCompanySelect({
  value,
  onChange,
  companies,
}: {
  value: string;
  onChange: (val: string) => void;
  companies: { id: string; name: string }[];
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');

  const selectedCompany = companies.find((c) => c.id === value);
  const filteredCompanies = companies.filter((c) =>
    (c.name || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-left text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center justify-between cursor-pointer"
      >
        <span className={selectedCompany ? 'text-slate-900 font-semibold' : 'text-slate-400'}>
          {selectedCompany ? selectedCompany.name : '-- Select Company --'}
        </span>
        <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
      </button>

      {isOpen && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-xl p-2 space-y-1.5 animate-in fade-in-50">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search company by name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-8 pl-8 pr-2 text-xs rounded-md border border-slate-200 bg-slate-50 text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
            />
          </div>

          <div className="max-h-40 overflow-y-auto space-y-0.5">
            <button
              type="button"
              onClick={() => {
                onChange('');
                setIsOpen(false);
                setSearch('');
              }}
              className="w-full px-2 py-1.5 text-left text-xs text-slate-500 hover:bg-slate-100 rounded cursor-pointer"
            >
              -- None / Clear Selection --
            </button>
            {filteredCompanies.length === 0 ? (
              <div className="px-2 py-2 text-xs text-slate-400 text-center">No matching companies</div>
            ) : (
              filteredCompanies.map((comp) => (
                <button
                  key={comp.id}
                  type="button"
                  onClick={() => {
                    onChange(comp.id);
                    setIsOpen(false);
                    setSearch('');
                  }}
                  className={`w-full px-2 py-1.5 text-left text-xs rounded transition flex items-center justify-between cursor-pointer ${
                    value === comp.id ? 'bg-blue-50 text-blue-700 font-bold' : 'text-slate-800 hover:bg-slate-100'
                  }`}
                >
                  <span>{comp.name}</span>
                  {value === comp.id && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0" />}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

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

  // Add Note Form State
  const [newNoteContent, setNewNoteContent] = useState('');

  // Queries
  const { data: contact, isLoading, refetch: refetchContact } = useContactQuery(contactId);
  const { data: companiesList = [] } = useCompaniesQuery(1, 100);

  // Sub-resource queries
  const { data: deals = [] } = useQuery({
    queryKey: ['contact-deals', contactId],
    queryFn: () => getContactDealsApi(contactId),
    enabled: !!contactId,
  });

  const { data: activities = [] } = useQuery({
    queryKey: ['contact-activities', contactId],
    queryFn: () => getContactActivitiesApi(contactId),
    enabled: !!contactId,
  });

  const { data: notes = [], refetch: refetchNotes } = useQuery({
    queryKey: ['contact-notes', contactId],
    queryFn: () => getContactNotesApi(contactId),
    enabled: !!contactId,
  });

  const { data: emails = [] } = useQuery({
    queryKey: ['contact-emails', contactId],
    queryFn: () => getContactEmailsApi(contactId),
    enabled: !!contactId,
  });

  const { data: calls = [] } = useQuery({
    queryKey: ['contact-calls', contactId],
    queryFn: () => getContactCallsApi(contactId),
    enabled: !!contactId,
  });

  // Mutations
  const updateContactMutation = useUpdateContactMutation();
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
      setIsEditModalOpen(true);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setErrorMessage(null);
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

        <div className="flex items-center gap-2 flex-wrap">
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

          <Button
            size="sm"
            variant="outline"
            onClick={openEditModal}
            className="border-slate-300 font-semibold text-xs gap-1.5 cursor-pointer"
          >
            <Edit className="w-4 h-4 text-blue-600" />
            <span>Edit Profile</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => setIsDeleteModalOpen(true)}
            className="border-rose-200 text-rose-600 hover:bg-rose-50 font-semibold text-xs gap-1.5 cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
            <span>Delete</span>
          </Button>
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

      {/* Sub-Resource Tabs Bar */}
      <div className="flex items-center border-b border-slate-200 gap-4 sm:gap-6 text-sm font-semibold text-slate-600 overflow-x-auto">
        <button
          onClick={() => setActiveTab('overview')}
          className={`pb-3 cursor-pointer transition border-b-2 flex items-center gap-2 shrink-0 whitespace-nowrap ${
            activeTab === 'overview' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>Overview & Timeline ({activities.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('deals')}
          className={`pb-3 cursor-pointer transition border-b-2 flex items-center gap-2 shrink-0 whitespace-nowrap ${
            activeTab === 'deals' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Briefcase className="w-4 h-4" />
          <span>Deals ({deals.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('notes')}
          className={`pb-3 cursor-pointer transition border-b-2 flex items-center gap-2 shrink-0 whitespace-nowrap ${
            activeTab === 'notes' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Notes ({notes.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('emails')}
          className={`pb-3 cursor-pointer transition border-b-2 flex items-center gap-2 shrink-0 whitespace-nowrap ${
            activeTab === 'emails' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          <span>Emails ({emails.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('calls')}
          className={`pb-3 cursor-pointer transition border-b-2 flex items-center gap-2 shrink-0 whitespace-nowrap ${
            activeTab === 'calls' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <PhoneCall className="w-4 h-4" />
          <span>Call Logs ({calls.length})</span>
        </button>
      </div>

      {/* TAB CONTENT: Overview */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Activity Timeline</h2>
          {activities.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No recent activity recorded for this contact.
            </div>
          ) : (
            <div className="space-y-2">
              {activities.map((act: any, idx: number) => (
                <div key={idx} className="p-3 bg-white rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-slate-900">{act.type || 'Activity Event'}</div>
                    <div className="text-slate-500 mt-0.5">{act.description || act.content || 'Contact updated'}</div>
                  </div>
                  <span className="text-[11px] text-slate-400">{act.created_at || 'Just now'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Deals */}
      {activeTab === 'deals' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Linked Sales Deals</h2>
          {deals.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No active sales pipeline deals associated with this contact.
            </div>
          ) : (
            <div className="space-y-2">
              {deals.map((deal: any) => (
                <div key={deal.id} className="p-4 bg-white rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                  <div>
                    <div className="font-bold text-slate-900">{deal.title}</div>
                    <div className="text-slate-500 mt-0.5 font-medium">Stage: {deal.stage}</div>
                  </div>
                  <div className="text-right font-bold text-blue-700 text-sm">
                    ${deal.amount ? deal.amount.toLocaleString() : '0'}
                  </div>
                </div>
              ))}
            </div>
          )}
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
          {notes.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No notes logged yet. Add your first note above.
            </div>
          ) : (
            <div className="space-y-2">
              {notes.map((note: any, idx: number) => (
                <div key={idx} className="p-4 bg-white rounded-xl border border-slate-200 text-xs space-y-1">
                  <div className="font-medium text-slate-900">{note.content}</div>
                  <div className="text-[10px] text-slate-400">{note.created_at || 'Saved'}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Emails */}
      {activeTab === 'emails' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Email History</h2>
          {emails.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No email messages sent or received.
            </div>
          ) : (
            <div className="space-y-2">
              {emails.map((email: any, idx: number) => (
                <div key={idx} className="p-4 bg-white rounded-xl border border-slate-200 text-xs space-y-1">
                  <div className="font-bold text-slate-900">{email.subject || 'Sales Outreach'}</div>
                  <div className="text-slate-600">{email.body_text || email.body || 'No preview body.'}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Calls */}
      {activeTab === 'calls' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Telephony Call Logs</h2>
          {calls.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No call logs recorded.
            </div>
          ) : (
            <div className="space-y-2">
              {calls.map((call: any, idx: number) => (
                <div key={idx} className="p-4 bg-white rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                  <div>
                    <div className="font-bold text-slate-900">{call.call_type || 'Outbound Call'}</div>
                    <div className="text-slate-500 mt-0.5">{call.notes || 'Routine check-in call'}</div>
                  </div>
                  <div className="text-right text-xs font-semibold text-slate-700">
                    {call.duration_seconds ? `${call.duration_seconds} sec` : '1 min'}
                  </div>
                </div>
              ))}
            </div>
          )}
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

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsEditModalOpen(false)} className="cursor-pointer">
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={updateContactMutation.isPending} className="bg-blue-600 text-white font-semibold cursor-pointer">
                {updateContactMutation.isPending ? 'Saving...' : 'Save Changes'}
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
