'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Mail,
  Phone,
  Building,
  User,
  Plus,
  Star,
  FileSpreadsheet,
  Upload,
  GitMerge,
  Trash2,
  Edit,
  CheckCircle2,
  AlertCircle,
  MoreVertical,
  X,
  Search,
  ChevronDown,
  Check
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { ConfirmModal } from '@/components/shared/confirm-modal';
import {
  useContactsQuery,
  useStarredContactsQuery,
  useCreateContactMutation,
  useUpdateContactMutation,
  useDeleteContactMutation,
  useStarContactMutation,
  useUnstarContactMutation,
  useMergeContactsMutation,
  useBulkDeleteContactsMutation,
  useImportContactsCsvMutation,
  exportContactsCsvApi,
  ContactItem
} from '@/lib/api/contacts';
import { useOrganizationsQuery } from '@/lib/api/organizations';
import { useCompaniesQuery } from '@/lib/api/companies';
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

export default function ContactsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<'all' | 'starred'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const limit = 15;

  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isMergeModalOpen, setIsMergeModalOpen] = useState(false);
  const [contactToEdit, setContactToEdit] = useState<ContactItem | null>(null);
  const [contactToDelete, setContactToDelete] = useState<ContactItem | null>(null);

  // Form State matching exact payload: first_name, last_name, name, email, phone, company_id, position, job_title
  const [formFirstName, setFormFirstName] = useState('');
  const [formLastName, setFormLastName] = useState('');
  const [formName, setFormName] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formPhone, setFormPhone] = useState('');
  const [formPosition, setFormPosition] = useState('');
  const [formJobTitle, setFormJobTitle] = useState('');
  const [formCompanyId, setFormCompanyId] = useState('');

  // Merge Form State
  const [primaryContactId, setPrimaryContactId] = useState('');
  const [secondaryContactId, setSecondaryContactId] = useState('');

  const resetForm = () => {
    setFormFirstName('');
    setFormLastName('');
    setFormName('');
    setFormEmail('');
    setFormPhone('');
    setFormPosition('');
    setFormJobTitle('');
    setFormCompanyId('');
  };

  // Search Debounce
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Queries
  const { data: allContacts = [], isLoading: isAllLoading, refetch: refetchAll } = useContactsQuery(page, limit, debouncedSearchTerm);
  const { data: starredContacts = [], isLoading: isStarredLoading, refetch: refetchStarred } = useStarredContactsQuery();
  const { data: organizations = [] } = useOrganizationsQuery();
  const { data: companiesList = [] } = useCompaniesQuery(1, 100);

  const contacts = activeTab === 'starred' ? starredContacts : allContacts;
  const isLoading = activeTab === 'starred' ? isStarredLoading : isAllLoading;

  // Mutations
  const createContactMutation = useCreateContactMutation();
  const updateContactMutation = useUpdateContactMutation();
  const deleteContactMutation = useDeleteContactMutation();
  const starContactMutation = useStarContactMutation();
  const unstarContactMutation = useUnstarContactMutation();
  const mergeContactsMutation = useMergeContactsMutation();
  const bulkDeleteMutation = useBulkDeleteContactsMutation();
  const importCsvMutation = useImportContactsCsvMutation();

  // Handlers
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const displayName = formName || `${formFirstName} ${formLastName}`.trim() || 'Contact';
    const emailVal = formEmail || 'user@example.com';
    try {
      setErrorMessage(null);
      await createContactMutation.mutateAsync({
        first_name: formFirstName || undefined,
        last_name: formLastName || undefined,
        name: displayName,
        email: emailVal,
        phone: formPhone || undefined,
        company_id: formCompanyId || undefined,
        position: formPosition || undefined,
        job_title: formJobTitle || formPosition || undefined,
      });
      setSuccessMessage(`Contact '${displayName}' created successfully.`);
      setIsCreateModalOpen(false);
      resetForm();
      refetchAll();
    } catch {
      setErrorMessage('Failed to create contact.');
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contactToEdit) return;
    try {
      setErrorMessage(null);
      const displayName = formName || `${formFirstName} ${formLastName}`.trim() || 'Contact';
      await updateContactMutation.mutateAsync({
        id: contactToEdit.id,
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
      setSuccessMessage(`Contact '${displayName}' updated successfully.`);
      setIsEditModalOpen(false);
      setContactToEdit(null);
      resetForm();
      refetchAll();
    } catch {
      setErrorMessage('Failed to update contact.');
    }
  };

  const openEditModal = (item: ContactItem) => {
    setContactToEdit(item);
    const parts = item.name ? item.name.split(' ') : [];
    setFormFirstName(parts[0] || '');
    setFormLastName(parts.slice(1).join(' ') || '');
    setFormName(item.name || '');
    setFormEmail(item.email || '');
    setFormPhone(item.phone || '');
    setFormPosition(item.position || '');
    setFormJobTitle(item.position || '');
    setFormCompanyId(item.company_id || '');
    setIsEditModalOpen(true);
  };

  const handleToggleStar = async (item: ContactItem) => {
    try {
      setErrorMessage(null);
      if (item.is_starred) {
        await unstarContactMutation.mutateAsync(item.id);
        setSuccessMessage(`Unstarred contact '${item.name}'.`);
      } else {
        await starContactMutation.mutateAsync(item.id);
        setSuccessMessage(`Starred contact '${item.name}'.`);
      }
      refetchAll();
      refetchStarred();
    } catch {
      setErrorMessage('Failed to update star status.');
    }
  };

  const handleConfirmDelete = async () => {
    if (!contactToDelete) return;
    try {
      setErrorMessage(null);
      await deleteContactMutation.mutateAsync(contactToDelete.id);
      setSuccessMessage(`Contact '${contactToDelete.name}' deleted successfully.`);
      setContactToDelete(null);
      refetchAll();
    } catch {
      setErrorMessage('Failed to delete contact.');
      setContactToDelete(null);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    if (confirm(`Are you sure you want to delete ${selectedIds.size} selected contact(s)?`)) {
      try {
        setErrorMessage(null);
        const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
        setSuccessMessage(res.message || `${selectedIds.size} contacts deleted successfully.`);
        setSelectedIds(new Set());
        refetchAll();
      } catch {
        setErrorMessage('Failed to bulk delete contacts.');
      }
    }
  };

  const handleExportCsv = async () => {
    try {
      setErrorMessage(null);
      const res = await exportContactsCsvApi();
      setSuccessMessage(`Contacts CSV exported. Download URL: ${res.download_url}`);
    } catch {
      setErrorMessage('Failed to export contacts CSV.');
    }
  };

  const handleImportCsv = async () => {
    try {
      setErrorMessage(null);
      const res = await importCsvMutation.mutateAsync();
      setSuccessMessage(res.message || 'Contacts imported from CSV successfully.');
      refetchAll();
    } catch {
      setErrorMessage('Failed to import contacts CSV.');
    }
  };

  const handleMergeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!primaryContactId || !secondaryContactId || primaryContactId === secondaryContactId) {
      setErrorMessage('Please select two distinct contact profiles to merge.');
      return;
    }
    try {
      setErrorMessage(null);
      const res = await mergeContactsMutation.mutateAsync({
        primaryId: primaryContactId,
        secondaryId: secondaryContactId,
      });
      setSuccessMessage(res.message || 'Contact profiles merged successfully.');
      setIsMergeModalOpen(false);
      refetchAll();
    } catch {
      setErrorMessage('Failed to merge contact profiles.');
    }
  };

  const columns: DataTableColumn<ContactItem>[] = [
    {
      id: 'star',
      header: '',
      cell: (item) => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            handleToggleStar(item);
          }}
          className="p-1 rounded text-amber-400 hover:text-amber-500 hover:bg-amber-50 transition cursor-pointer"
          title={item.is_starred ? 'Unstar Contact' : 'Star Contact'}
        >
          <Star className={`w-4 h-4 ${item.is_starred ? 'fill-amber-400' : ''}`} />
        </button>
      ),
    },
    {
      id: 'name',
      header: 'Contact Name',
      cell: (item) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-blue-700 font-bold text-xs shrink-0">
            {item.name ? item.name.charAt(0).toUpperCase() : 'C'}
          </div>
          <div>
            <Link href={`/contacts/${item.id}`} className="font-bold text-slate-900 text-xs hover:text-blue-600 hover:underline">
              {item.name}
            </Link>
            <div className="text-[11px] text-slate-500">{item.position || 'Representative'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'email',
      header: 'Email Address',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-semibold">
          <Mail className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <span>{item.email}</span>
        </div>
      ),
    },
    {
      id: 'phone',
      header: 'Phone Number',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-600 text-xs font-medium">
          <Phone className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <span>{item.phone || 'N/A'}</span>
        </div>
      ),
    },
    {
      id: 'company',
      header: 'Company / Org',
      cell: (item) => {
        const foundCompany = companiesList.find((c) => c.id === item.company_id);
        const foundOrg = organizations.find((o) => o.id === item.company_id);
        const companyLabel = foundCompany?.name || foundOrg?.name || (item.company_id ? 'Enterprise Partner' : 'Primary Org');
        return (
          <div className="flex items-center gap-1.5 text-slate-700 text-xs font-semibold">
            <Building className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            <span>{companyLabel}</span>
          </div>
        );
      },
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: (item) => (
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => openEditModal(item)}
            className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded transition cursor-pointer"
            title="Edit contact"
          >
            <Edit className="w-3.5 h-3.5" />
          </button>

          <button
            type="button"
            onClick={() => setContactToDelete(item)}
            className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition cursor-pointer"
            title="Delete contact"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2.5">
            <User className="w-6 h-6 text-blue-600" />
            <span>Contact Directory</span>
          </h1>
          <p className="text-xs font-medium text-slate-500 mt-1">
            Manage customer contacts, starred profiles, contact merges, and bulk operations.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            size="sm"
            onClick={() => {
              resetForm();
              setIsCreateModalOpen(true);
            }}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs gap-1.5 cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Add Contact</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={handleExportCsv}
            className="border-slate-300 font-semibold text-xs gap-1 cursor-pointer"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
            <span>Export CSV</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={handleImportCsv}
            disabled={importCsvMutation.isPending}
            className="border-slate-300 font-semibold text-xs gap-1 cursor-pointer"
          >
            <Upload className="w-3.5 h-3.5 text-blue-600" />
            <span>Import CSV</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => setIsMergeModalOpen(true)}
            className="border-slate-300 font-semibold text-xs gap-1 cursor-pointer"
          >
            <GitMerge className="w-3.5 h-3.5 text-purple-600" />
            <span>Merge</span>
          </Button>

          {selectedIds.size > 0 && (
            <Button
              size="sm"
              variant="outline"
              onClick={handleBulkDelete}
              className="border-rose-300 text-rose-600 hover:bg-rose-50 font-semibold text-xs gap-1 cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Delete Selected ({selectedIds.size})</span>
            </Button>
          )}
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

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center border-b border-slate-200 gap-6 text-sm font-semibold text-slate-600">
        <button
          onClick={() => {
            setActiveTab('all');
            setPage(1);
          }}
          className={`pb-3 cursor-pointer transition border-b-2 flex items-center gap-2 ${
            activeTab === 'all' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <span>All Contacts</span>
          <Badge variant="outline" className="bg-slate-100 text-slate-700 text-[10px]">
            {allContacts.length}
          </Badge>
        </button>

        <button
          onClick={() => {
            setActiveTab('starred');
            setPage(1);
          }}
          className={`pb-3 cursor-pointer transition border-b-2 flex items-center gap-2 ${
            activeTab === 'starred' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Star className="w-3.5 h-3.5 text-amber-500 fill-amber-400" />
          <span>Starred Contacts</span>
          <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200 text-[10px]">
            {starredContacts.length}
          </Badge>
        </button>
      </div>

      {/* Search Input Bar */}
      <div className="relative max-w-md">
        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
        <Input
          type="text"
          placeholder="Search contacts by name or email..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-9 h-9 text-xs"
        />
      </div>

      {/* Contacts DataTable */}
      <DataTable
        columns={columns as any}
        data={contacts as any}
        getRowKey={(item: any) => item.id}
        onRowClick={(item: any) => router.push(`/contacts/${item.id}`)}
        emptyTitle="No contacts found"
        emptyDescription="Create your first contact profile or import CSV data."
        showCheckbox
        selectedIds={selectedIds}
        onToggleAllRows={(checked) => {
          if (checked) {
            setSelectedIds(new Set(contacts.map((c) => c.id)));
          } else {
            setSelectedIds(new Set());
          }
        }}
        onToggleRow={(item: any, checked) => {
          const next = new Set(selectedIds);
          if (checked) next.add(item.id);
          else next.delete(item.id);
          setSelectedIds(next);
        }}
        pagination={{
          pageIndex: page - 1,
          pageCount: Math.ceil((contacts.length || 1) / limit) || 1,
          onPageChange: (pIndex) => setPage(pIndex + 1),
          totalRecords: contacts.length,
        }}
      />

      {/* CREATE CONTACT MODAL */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-md bg-white rounded-2xl border border-slate-300 shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <User className="w-5 h-5 text-blue-600" />
                <span>Create New Contact</span>
              </h3>
              <button type="button" onClick={() => setIsCreateModalOpen(false)} className="text-slate-400 hover:text-slate-700 cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">First Name</Label>
                  <Input
                    type="text"
                    placeholder="e.g. selva"
                    value={formFirstName}
                    onChange={(e) => setFormFirstName(e.target.value)}
                    className="h-9 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Last Name</Label>
                  <Input
                    type="text"
                    placeholder="e.g. kumar"
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
                  placeholder="e.g. selvakumar"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Email Address</Label>
                  <Input
                    type="text"
                    placeholder="user@example.com"
                    value={formEmail}
                    onChange={(e) => setFormEmail(e.target.value)}
                    className="h-9 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Phone Number</Label>
                  <Input
                    type="text"
                    placeholder="7374837284"
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

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Position</Label>
                  <Input
                    type="text"
                    placeholder="e.g. frontend"
                    value={formPosition}
                    onChange={(e) => setFormPosition(e.target.value)}
                    className="h-9 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Job Title</Label>
                  <Input
                    type="text"
                    placeholder="e.g. software"
                    value={formJobTitle}
                    onChange={(e) => setFormJobTitle(e.target.value)}
                    className="h-9 text-xs"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setIsCreateModalOpen(false)} className="cursor-pointer">
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={createContactMutation.isPending} className="bg-blue-600 text-white font-semibold cursor-pointer">
                  {createContactMutation.isPending ? 'Creating...' : 'Create Contact'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT CONTACT MODAL */}
      {isEditModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-md bg-white rounded-2xl border border-slate-300 shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <Edit className="w-5 h-5 text-blue-600" />
                <span>Edit Contact Profile</span>
              </h3>
              <button type="button" onClick={() => setIsEditModalOpen(false)} className="text-slate-400 hover:text-slate-700 cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
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

              <div className="grid grid-cols-2 gap-3">
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

              <div className="grid grid-cols-2 gap-3">
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

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setIsEditModalOpen(false)} className="cursor-pointer">
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={updateContactMutation.isPending} className="bg-blue-600 text-white font-semibold cursor-pointer">
                  {updateContactMutation.isPending ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MERGE CONTACTS MODAL */}
      {isMergeModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-md bg-white rounded-2xl border border-slate-300 shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <GitMerge className="w-5 h-5 text-purple-600" />
                <span>Merge Contact Profiles</span>
              </h3>
              <button type="button" onClick={() => setIsMergeModalOpen(false)} className="text-slate-400 hover:text-slate-700 cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleMergeSubmit} className="space-y-4 text-xs">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Primary Contact (To Keep)</Label>
                <select
                  value={primaryContactId}
                  onChange={(e) => setPrimaryContactId(e.target.value)}
                  className="w-full h-9 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-900"
                >
                  <option value="">Select primary contact...</option>
                  {allContacts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.email})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Secondary Contact (To Merge & Remove)</Label>
                <select
                  value={secondaryContactId}
                  onChange={(e) => setSecondaryContactId(e.target.value)}
                  className="w-full h-9 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-900"
                >
                  <option value="">Select secondary contact...</option>
                  {allContacts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.email})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setIsMergeModalOpen(false)} className="cursor-pointer">
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={mergeContactsMutation.isPending} className="bg-purple-600 hover:bg-purple-700 text-white font-semibold cursor-pointer">
                  {mergeContactsMutation.isPending ? 'Merging...' : 'Merge Profiles'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CONFIRM DELETE MODAL */}
      <ConfirmModal
        isOpen={!!contactToDelete}
        onClose={() => setContactToDelete(null)}
        onConfirm={handleConfirmDelete}
        title="Delete Contact Profile"
        description="This action cannot be undone."
        confirmText="Delete Contact"
        variant="danger"
        isLoading={deleteContactMutation.isPending}
        message={
          contactToDelete && (
            <p>
              Are you sure you want to delete contact <strong className="text-slate-900">{contactToDelete.name}</strong> ({contactToDelete.email})?
            </p>
          )
        }
      />
    </div>
  );
}
