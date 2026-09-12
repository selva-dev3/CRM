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
  Calendar
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import { PageTabs } from '@/components/common/page-tabs';
import {
  CompanyContactsTable,
  CompanyDealsTable,
  CompanyDocumentsTable,
  CompanyInvoicesTable,
  CompanyNotesTable,
  CompanyQuotesTable,
  CompanyRelationshipError,
} from '@/components/features/companies/company-relationship-tables';
import {
  useCompanyQuery,
  useUpdateCompanyMutation,
  useDeleteCompanyMutation,
  useCompanyContactsQuery,
  useCompanyDealsQuery,
  useCompanyNotesQuery,
  useCompanyQuotesQuery,
  useCompanyInvoicesQuery,
  useCompanyDocumentsQuery,
  useCompanyHierarchyQuery,
  useAddCompanyNoteMutation,
} from '@/lib/api/companies';
import { ApiError } from '@/lib/api/client';
import { CustomFieldValues } from '@/components/common/custom-field-values';
import { CustomFields } from '@/components/common/custom-fields';
import {
  useEntityCustomFieldsQuery,
  type CustomFieldValue,
} from '@/lib/api/custom-fields';

export default function CompanyDetailsPage() {
  const params = useParams();
  const router = useRouter();

  const companyId = (params.id as string) || '';

  const [activeTab, setActiveTab] = useState<
    'contacts' | 'deals' | 'notes' | 'quotes' | 'invoices' | 'documents' | 'hierarchy'
  >('contacts');

  const [newNoteContent, setNewNoteContent] = useState('');
  const relationshipLimit = 15;
  const [contactsPage, setContactsPage] = useState(1);
  const [dealsPage, setDealsPage] = useState(1);
  const [notesPage, setNotesPage] = useState(1);
  const [quotesPage, setQuotesPage] = useState(1);
  const [invoicesPage, setInvoicesPage] = useState(1);
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

  // Relationship data is loaded only when its tab is active. A failure in one
  // relationship must not put every other tab into an error state.
  const contactsQuery = useCompanyContactsQuery(companyId, activeTab === 'contacts', contactsPage, relationshipLimit);
  const dealsQuery = useCompanyDealsQuery(companyId, activeTab === 'deals', dealsPage, relationshipLimit);
  const notesQuery = useCompanyNotesQuery(companyId, activeTab === 'notes', notesPage, relationshipLimit);
  const quotesQuery = useCompanyQuotesQuery(companyId, activeTab === 'quotes', quotesPage, relationshipLimit);
  const invoicesQuery = useCompanyInvoicesQuery(companyId, activeTab === 'invoices', invoicesPage, relationshipLimit);
  const documentsQuery = useCompanyDocumentsQuery(companyId, activeTab === 'documents');
  const hierarchyQuery = useCompanyHierarchyQuery(companyId, activeTab === 'hierarchy');

  const contacts = contactsQuery.data?.items ?? [];
  const deals = dealsQuery.data?.items ?? [];
  const notes = notesQuery.data?.items ?? [];
  const quotes = quotesQuery.data?.items ?? [];
  const invoices = invoicesQuery.data?.items ?? [];
  const documents = documentsQuery.data ?? [];
  const hierarchy = hierarchyQuery.data;

  // Mutations
  const updateCompanyMutation = useUpdateCompanyMutation();
  const deleteCompanyMutation = useDeleteCompanyMutation();
  const addNoteMutation = useAddCompanyNoteMutation(companyId);
  const isDocumentsUnavailable =
    documentsQuery.error instanceof ApiError &&
    documentsQuery.error.code === 'COMPANY_DOCUMENT_RELATION_UNAVAILABLE';

  const handleAddNote = () => {
    setErrorMessage(null);
    addNoteMutation.mutate(newNoteContent.trim(), {
      onSuccess: () => {
        setSuccessMessage('Company note added successfully.');
        setNewNoteContent('');
        setNotesPage(1);
      },
      onError: () => {
        setErrorMessage('Failed to add company note.');
      },
    });
  };

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
          { value: 'contacts', icon: <User className="size-4" />, label: contactsQuery.data ? `Contacts (${contactsQuery.data.total})` : 'Contacts' },
          { value: 'deals', icon: <Briefcase className="size-4" />, label: dealsQuery.data ? `Deals (${dealsQuery.data.total})` : 'Deals' },
          { value: 'notes', icon: <FileText className="size-4" />, label: notesQuery.data ? `Notes (${notesQuery.data.total})` : 'Notes' },
          { value: 'quotes', icon: <DollarSign className="size-4" />, label: quotesQuery.data ? `Quotes (${quotesQuery.data.total})` : 'Quotes' },
          { value: 'invoices', icon: <FileSpreadsheet className="size-4" />, label: invoicesQuery.data ? `Invoices (${invoicesQuery.data.total})` : 'Invoices' },
          { value: 'documents', icon: <Folder className="size-4" />, label: documentsQuery.data ? `Documents (${documents.length})` : 'Documents' },
          { value: 'hierarchy', icon: <Network className="size-4" />, label: 'Corporate Hierarchy' },
        ]}
        listClassName="border-b border-slate-200"
      />

      {/* TAB CONTENT: Contacts */}
      {activeTab === 'contacts' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Associated Contact Profiles</h2>
          {contactsQuery.isError ? (
            <CompanyRelationshipError
              resourceName="Contacts"
              onRetry={() => void contactsQuery.refetch()}
            />
          ) : (
            <CompanyContactsTable
              data={contacts}
              isLoading={contactsQuery.isLoading}
              onRowClick={(contact) => router.push(`/contacts/${contact.id}`)}
              pagination={{ pageIndex: contactsPage - 1, pageCount: Math.max(1, Math.ceil((contactsQuery.data?.total ?? 0) / relationshipLimit)), totalRecords: contactsQuery.data?.total ?? 0, onPageChange: (value) => setContactsPage(value + 1) }}
            />
          )}
        </div>
      )}

      {/* TAB CONTENT: Deals */}
      {activeTab === 'deals' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Linked Sales Pipeline Deals</h2>
          {dealsQuery.isError ? (
            <CompanyRelationshipError
              resourceName="Deals"
              onRetry={() => void dealsQuery.refetch()}
            />
          ) : (
            <CompanyDealsTable
              data={deals}
              isLoading={dealsQuery.isLoading}
              onRowClick={(deal) => router.push(`/deals/${deal.id}`)}
              pagination={{ pageIndex: dealsPage - 1, pageCount: Math.max(1, Math.ceil((dealsQuery.data?.total ?? 0) / relationshipLimit)), totalRecords: dealsQuery.data?.total ?? 0, onPageChange: (value) => setDealsPage(value + 1) }}
            />
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
                onClick={handleAddNote}
                disabled={!newNoteContent.trim() || addNoteMutation.isPending}
                className="bg-blue-600 text-white font-semibold text-xs gap-1 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>Add Note</span>
              </Button>
            </div>
          </div>

          <h2 className="text-sm font-bold text-slate-900 pt-2">Company Notes Log</h2>
          {notesQuery.isError ? (
            <CompanyRelationshipError
              resourceName="Notes"
              onRetry={() => void notesQuery.refetch()}
            />
          ) : (
            <CompanyNotesTable data={notes} isLoading={notesQuery.isLoading} pagination={{ pageIndex: notesPage - 1, pageCount: Math.max(1, Math.ceil((notesQuery.data?.total ?? 0) / relationshipLimit)), totalRecords: notesQuery.data?.total ?? 0, onPageChange: (value) => setNotesPage(value + 1) }} />
          )}
        </div>
      )}

      {/* TAB CONTENT: Quotes */}
      {activeTab === 'quotes' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Generated Price Quotes</h2>
          {quotesQuery.isError ? (
            <CompanyRelationshipError
              resourceName="Quotes"
              onRetry={() => void quotesQuery.refetch()}
            />
          ) : (
            <CompanyQuotesTable
              data={quotes}
              isLoading={quotesQuery.isLoading}
              onRowClick={(quote) => router.push(`/quotes/${quote.id}`)}
              pagination={{ pageIndex: quotesPage - 1, pageCount: Math.max(1, Math.ceil((quotesQuery.data?.total ?? 0) / relationshipLimit)), totalRecords: quotesQuery.data?.total ?? 0, onPageChange: (value) => setQuotesPage(value + 1) }}
            />
          )}
        </div>
      )}

      {/* TAB CONTENT: Invoices */}
      {activeTab === 'invoices' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Billed Invoices</h2>
          {invoicesQuery.isError ? (
            <CompanyRelationshipError
              resourceName="Invoices"
              onRetry={() => void invoicesQuery.refetch()}
            />
          ) : (
            <CompanyInvoicesTable
              data={invoices}
              isLoading={invoicesQuery.isLoading}
              onRowClick={(invoice) => router.push(`/invoices/${invoice.id}`)}
              pagination={{ pageIndex: invoicesPage - 1, pageCount: Math.max(1, Math.ceil((invoicesQuery.data?.total ?? 0) / relationshipLimit)), totalRecords: invoicesQuery.data?.total ?? 0, onPageChange: (value) => setInvoicesPage(value + 1) }}
            />
          )}
        </div>
      )}

      {/* TAB CONTENT: Documents */}
      {activeTab === 'documents' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Attached Documents & Files</h2>
          {documentsQuery.isError ? (
            <CompanyRelationshipError
              resourceName="Documents"
              unavailable={isDocumentsUnavailable}
              onRetry={() => void documentsQuery.refetch()}
            />
          ) : (
            <CompanyDocumentsTable data={documents} isLoading={documentsQuery.isLoading} />
          )}
        </div>
      )}

      {/* TAB CONTENT: Corporate Hierarchy */}
      {activeTab === 'hierarchy' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Corporate Structure & Subsidiaries</h2>
          {hierarchyQuery.isError ? (
            <CompanyRelationshipError
              resourceName="Corporate hierarchy"
              onRetry={() => void hierarchyQuery.refetch()}
            />
          ) : hierarchyQuery.isLoading ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-xs font-medium text-slate-500">
              Loading corporate hierarchy...
            </div>
          ) : (
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
                    {hierarchy.subsidiaries.map((sub) => (
                      <div key={sub.id} className="p-3 bg-slate-50 rounded-lg border border-slate-200 font-semibold text-slate-900">
                        {sub.name} ({sub.domain || 'Subsidiary Branch'})
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
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
