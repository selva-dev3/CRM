'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Building2,
  Globe,
  Briefcase,
  Users,
  Edit,
  Trash2,
  User,
  FileText,
  DollarSign,
  FileSpreadsheet,
  Folder,
  Network,
  Plus,
  CheckCircle2,
  AlertCircle,
  Mail,
  Phone,
  Calendar
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import { PageTabs } from '@/components/common/page-tabs';
import {
  useCompanyQuery,
  useUpdateCompanyMutation,
  useDeleteCompanyMutation,
  getCompanyContactsApi,
  getCompanyDealsApi,
  getCompanyNotesApi,
  addCompanyNoteApi,
  getCompanyQuotesApi,
  getCompanyInvoicesApi,
  getCompanyDocumentsApi,
  getCompanyHierarchyApi
} from '@/lib/api/companies';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { CustomFieldValues } from '@/components/common/custom-field-values';
import { CustomFields } from '@/components/common/custom-fields';
import {
  useEntityCustomFieldsQuery,
  type CustomFieldValue,
} from '@/lib/api/custom-fields';

export default function CompanyDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();

  const companyId = (params.id as string) || '';

  const [activeTab, setActiveTab] = useState<
    'contacts' | 'deals' | 'notes' | 'quotes' | 'invoices' | 'documents' | 'hierarchy'
  >('contacts');

  const [newNoteContent, setNewNoteContent] = useState('');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modals
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  // Edit Form State
  const [formName, setFormName] = useState('');
  const [formDomain, setFormDomain] = useState('');
  const [formWebsite, setFormWebsite] = useState('');
  const [formIndustry, setFormIndustry] = useState('');
  const [formSize, setFormSize] = useState('');
  const [formEmployeeCount, setFormEmployeeCount] = useState<number | ''>('');
  const [formCustomFields, setFormCustomFields] = useState<
    Record<string, CustomFieldValue>
  >({});

  // Main Company Data Query
  const { data: company, isLoading, isError, refetch } = useCompanyQuery(companyId);
  const {
    data: customFields = [],
    isLoading: isCustomFieldsLoading,
    isError: isCustomFieldsError,
  } = useEntityCustomFieldsQuery('Company');

  // Sub-resource queries
  const { data: contacts = [] } = useQuery({
    queryKey: ['company-contacts', companyId],
    queryFn: () => getCompanyContactsApi(companyId),
    enabled: !!companyId,
  });

  const { data: deals = [] } = useQuery({
    queryKey: ['company-deals', companyId],
    queryFn: () => getCompanyDealsApi(companyId),
    enabled: !!companyId,
  });

  const { data: notes = [], refetch: refetchNotes } = useQuery({
    queryKey: ['company-notes', companyId],
    queryFn: () => getCompanyNotesApi(companyId),
    enabled: !!companyId,
  });

  const { data: quotes = [] } = useQuery({
    queryKey: ['company-quotes', companyId],
    queryFn: () => getCompanyQuotesApi(companyId),
    enabled: !!companyId,
  });

  const { data: invoices = [] } = useQuery({
    queryKey: ['company-invoices', companyId],
    queryFn: () => getCompanyInvoicesApi(companyId),
    enabled: !!companyId,
  });

  const { data: documents = [] } = useQuery({
    queryKey: ['company-documents', companyId],
    queryFn: () => getCompanyDocumentsApi(companyId),
    enabled: !!companyId,
  });

  const { data: hierarchy } = useQuery({
    queryKey: ['company-hierarchy', companyId],
    queryFn: () => getCompanyHierarchyApi(companyId),
    enabled: !!companyId,
  });

  // Mutations
  const updateCompanyMutation = useUpdateCompanyMutation();
  const deleteCompanyMutation = useDeleteCompanyMutation();

  const addNoteMutation = useMutation({
    mutationFn: (content: string) => addCompanyNoteApi({ id: companyId, content }),
    onSuccess: () => {
      setSuccessMessage('Company note added successfully.');
      setNewNoteContent('');
      refetchNotes();
      queryClient.invalidateQueries({ queryKey: ['company-notes', companyId] });
    },
    onError: () => {
      setErrorMessage('Failed to add company note.');
    },
  });

  const openEditModal = () => {
    if (!company) return;
    setFormName(company.name || '');
    setFormDomain(company.domain || '');
    setFormWebsite(company.website || '');
    setFormIndustry(company.industry || '');
    setFormSize(company.size || '');
    setFormEmployeeCount(company.employee_count ?? '');
    setFormCustomFields(company.custom_fields ?? {});
    setIsEditModalOpen(true);
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyId) return;
    try {
      setErrorMessage(null);
      await updateCompanyMutation.mutateAsync({
        id: companyId,
        data: {
          name: formName,
          domain: formDomain || undefined,
          website: formWebsite || undefined,
          industry: formIndustry || undefined,
          size: formSize || (formEmployeeCount ? String(formEmployeeCount) : undefined),
          employee_count: formEmployeeCount !== '' ? Number(formEmployeeCount) : undefined,
          custom_fields: formCustomFields,
        },
      });
      setSuccessMessage('Company profile updated successfully.');
      setIsEditModalOpen(false);
      refetch();
    } catch {
      setErrorMessage('Failed to update company profile.');
    }
  };

  const handleConfirmDelete = async () => {
    try {
      setErrorMessage(null);
      await deleteCompanyMutation.mutateAsync(companyId);
      router.push('/companies');
    } catch {
      setErrorMessage('Failed to delete company.');
      setIsDeleteModalOpen(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 text-center text-xs font-semibold text-slate-500">
        Loading company details...
      </div>
    );
  }

  if (isError || !company) {
    return (
      <div className="space-y-4 p-6">
        <Link href="/companies" className="inline-flex items-center text-xs font-bold text-blue-600 hover:underline gap-1">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Companies Directory
        </Link>
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-900 text-xs font-medium">
          Company profile not found or an error occurred.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <Link href="/companies" className="inline-flex items-center text-xs font-bold text-slate-500 hover:text-blue-600 transition gap-1 mb-2">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Companies Directory
          </Link>
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center text-white font-black text-xl shadow-md">
              <Building2 className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">{company.name}</h1>
              <p className="text-xs font-medium text-slate-500">
                {company.industry || 'General Business'} &bull; {company.website || company.domain || 'Enterprise Account'}
              </p>
            </div>
          </div>
        </div>

        {/* Action Header Buttons */}
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={openEditModal}
            className="border-slate-300 font-semibold text-xs gap-1.5 cursor-pointer"
          >
            <Edit className="w-3.5 h-3.5 text-blue-600" />
            <span>Edit Company</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => setIsDeleteModalOpen(true)}
            className="border-rose-300 text-rose-600 hover:bg-rose-50 font-semibold text-xs gap-1.5 cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Delete</span>
          </Button>
        </div>
      </div>

      {/* Feedback Notifications */}
      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs font-medium flex items-center gap-2 animate-in fade-in-50">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs font-medium flex items-center gap-2 animate-in fade-in-50">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Profile Overview Card */}
      <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-4">
        <h2 className="text-sm font-bold text-slate-900">Organization Overview</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
            <span className="text-slate-400 font-medium flex items-center gap-1">
              <Globe className="w-3.5 h-3.5 text-blue-500" /> Website / Domain
            </span>
            <span className="font-semibold text-blue-600 truncate block">
              {company.website ? (
                <a href={company.website.startsWith('http') ? company.website : `https://${company.website}`} target="_blank" rel="noreferrer" className="hover:underline">
                  {company.website}
                </a>
              ) : (
                company.domain || 'N/A'
              )}
            </span>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
            <span className="text-slate-400 font-medium flex items-center gap-1">
              <Briefcase className="w-3.5 h-3.5 text-slate-500" /> Industry Sector
            </span>
            <span className="font-semibold text-slate-800">{company.industry || 'General Corporate'}</span>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
            <span className="text-slate-400 font-medium flex items-center gap-1">
              <Users className="w-3.5 h-3.5 text-indigo-500" /> Organization Size
            </span>
            <span className="font-semibold text-slate-800">
              {company.employee_count ? `${company.employee_count} employees` : company.size ? `${company.size} staff` : 'Enterprise'}
            </span>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
            <span className="text-slate-400 font-medium flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-amber-500" /> Created Date
            </span>
            <span className="font-semibold text-slate-800">
              {company.created_at ? new Date(company.created_at).toLocaleDateString() : 'Recent'}
            </span>
          </div>
        </div>
      </div>

      <CustomFieldValues fields={customFields} values={company.custom_fields ?? {}} />

      <PageTabs
        value={activeTab}
        onValueChange={setActiveTab}
        tabs={[
          { value: 'contacts', icon: <User className="size-4" />, label: `Contacts (${contacts.length})` },
          { value: 'deals', icon: <Briefcase className="size-4" />, label: `Deals (${deals.length})` },
          { value: 'notes', icon: <FileText className="size-4" />, label: `Notes (${notes.length})` },
          { value: 'quotes', icon: <DollarSign className="size-4" />, label: `Quotes (${quotes.length})` },
          { value: 'invoices', icon: <FileSpreadsheet className="size-4" />, label: `Invoices (${invoices.length})` },
          { value: 'documents', icon: <Folder className="size-4" />, label: `Documents (${documents.length})` },
          { value: 'hierarchy', icon: <Network className="size-4" />, label: 'Corporate Hierarchy' },
        ]}
        listClassName="border-b border-slate-200"
      />

      {/* TAB CONTENT: Contacts */}
      {activeTab === 'contacts' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Associated Contact Profiles</h2>
          {contacts.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No contacts associated with this company profile yet.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {contacts.map((contact) => (
                <div key={contact.id} className="p-4 bg-white rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-blue-100 text-blue-700 font-bold flex items-center justify-center text-xs">
                      {contact.name ? contact.name.charAt(0).toUpperCase() : 'C'}
                    </div>
                    <div>
                      <Link href={`/contacts/${contact.id}`} className="font-bold text-slate-900 hover:text-blue-600 hover:underline">
                        {contact.name || `${contact.first_name || ''} ${contact.last_name || ''}`}
                      </Link>
                      <div className="text-slate-500 text-[11px]">{contact.position || contact.job_title || 'Representative'}</div>
                    </div>
                  </div>
                  <div className="text-right space-y-0.5">
                    <div className="text-slate-600 flex items-center gap-1 justify-end">
                      <Mail className="w-3 h-3 text-slate-400" />
                      <span>{contact.email}</span>
                    </div>
                    {contact.phone && (
                      <div className="text-slate-400 text-[11px] flex items-center gap-1 justify-end">
                        <Phone className="w-3 h-3 text-slate-400" />
                        <span>{contact.phone}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Deals */}
      {activeTab === 'deals' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Linked Sales Pipeline Deals</h2>
          {deals.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No deals linked to this company profile yet.
            </div>
          ) : (
            <div className="space-y-2">
              {deals.map((deal) => (
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
              placeholder="Type note details for this company..."
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

          <h2 className="text-sm font-bold text-slate-900 pt-2">Company Notes Log</h2>
          {notes.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No notes logged yet for this company. Add your first note above.
            </div>
          ) : (
            <div className="space-y-2">
              {notes.map((note, idx: number) => (
                <div key={idx} className="p-4 bg-white rounded-xl border border-slate-200 text-xs space-y-1">
                  <div className="font-medium text-slate-900">{note.content}</div>
                  <div className="text-[10px] text-slate-400">{note.created_at || 'Saved'}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Quotes */}
      {activeTab === 'quotes' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Generated Price Quotes</h2>
          {quotes.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No quotes generated for this company yet.
            </div>
          ) : (
            <div className="space-y-2">
              {quotes.map((quote, idx: number) => (
                <div key={idx} className="p-4 bg-white rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                  <div>
                    <div className="font-bold text-slate-900">{quote.title || `Quote #${quote.id}`}</div>
                    <div className="text-slate-500 text-[11px] font-medium">Status: {quote.status || 'Draft'}</div>
                  </div>
                  <div className="text-right font-bold text-emerald-700 text-sm">
                    ${quote.total_amount ? quote.total_amount.toLocaleString() : '0'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Invoices */}
      {activeTab === 'invoices' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Billed Invoices</h2>
          {invoices.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No invoices generated or billed to this company.
            </div>
          ) : (
            <div className="space-y-2">
              {invoices.map((inv, idx: number) => (
                <div key={idx} className="p-4 bg-white rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                  <div>
                    <div className="font-bold text-slate-900">Invoice #{inv.number || inv.id}</div>
                    <div className="text-slate-500 text-[11px] font-medium">Status: {inv.status || 'Unpaid'}</div>
                  </div>
                  <div className="text-right font-bold text-blue-700 text-sm">
                    ${inv.amount_due ? inv.amount_due.toLocaleString() : '0'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Documents */}
      {activeTab === 'documents' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Attached Documents & Files</h2>
          {documents.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No files or contract documents uploaded for this company.
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc, idx: number) => (
                <div key={idx} className="p-4 bg-white rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <Folder className="w-4 h-4 text-blue-600" />
                    <div>
                      <div className="font-bold text-slate-900">{doc.name || 'Contract Document'}</div>
                      <div className="text-slate-400 text-[10px]">{doc.file_type || 'PDF Document'}</div>
                    </div>
                  </div>
                  <a href={doc.file_url || '#'} target="_blank" rel="noreferrer" className="text-blue-600 font-semibold hover:underline">
                    Download
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Corporate Hierarchy */}
      {activeTab === 'hierarchy' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Corporate Structure & Subsidiaries</h2>
          <div className="p-6 bg-white rounded-2xl border border-slate-200 space-y-4 text-xs">
            <div className="flex items-center gap-2 font-semibold text-slate-800">
              <Network className="w-4 h-4 text-blue-600" />
              <span>Parent Organization: {hierarchy?.parent_company ? hierarchy.parent_company.name : 'Independent Account (No Parent)'}</span>
            </div>
            <div className="border-t border-slate-100 pt-3">
              <h3 className="font-semibold text-slate-700 mb-2">Subsidiary Entities ({hierarchy?.subsidiaries?.length || 0})</h3>
              {!hierarchy?.subsidiaries || hierarchy.subsidiaries.length === 0 ? (
                <p className="text-slate-400">No child corporate entities registered under this account.</p>
              ) : (
                <div className="space-y-1.5">
                  {hierarchy.subsidiaries.map((sub, idx: number) => (
                    <div key={idx} className="p-3 bg-slate-50 rounded-lg border border-slate-200 font-semibold text-slate-900">
                      {sub.name} ({sub.domain || 'Subsidiary Branch'})
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* EDIT COMPANY MODAL */}
      {isEditModalOpen && (
        <ModalShell
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          size="md"
          title={
            <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
              <Edit className="w-5 h-5 text-blue-600" />
              <span>Edit Company Profile</span>
            </h3>
          }
        >
          <form onSubmit={handleEditSubmit} className="space-y-4 text-xs">
            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Company Name</Label>
              <Input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Domain Handle</Label>
                <Input
                  type="text"
                  value={formDomain}
                  onChange={(e) => setFormDomain(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Website URL</Label>
                <Input
                  type="text"
                  value={formWebsite}
                  onChange={(e) => setFormWebsite(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Industry Sector</Label>
              <Input
                type="text"
                value={formIndustry}
                onChange={(e) => setFormIndustry(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Size String</Label>
                <Input
                  type="text"
                  value={formSize}
                  onChange={(e) => setFormSize(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Employee Count</Label>
                <Input
                  type="number"
                  value={formEmployeeCount}
                  onChange={(e) => setFormEmployeeCount(e.target.value !== '' ? Number(e.target.value) : '')}
                  className="h-9 text-xs"
                />
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
              idPrefix="company-detail-edit"
            />

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsEditModalOpen(false)} className="cursor-pointer">
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={updateCompanyMutation.isPending} className="bg-blue-600 text-white font-semibold cursor-pointer">
                {updateCompanyMutation.isPending ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* DELETE CONFIRM MODAL */}
      <ConfirmModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onConfirm={handleConfirmDelete}
        title="Delete Company Profile"
        description="This action cannot be undone."
        confirmText="Delete Company"
        variant="danger"
        isLoading={deleteCompanyMutation.isPending}
        message={
          <p>
            Are you sure you want to delete company <strong className="text-slate-900">{company.name}</strong>?
          </p>
        }
      />
    </div>
  );
}
