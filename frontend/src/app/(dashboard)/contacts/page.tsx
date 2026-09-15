'use client';

import { ResponsiveSelect } from '@/components/common/responsive-select';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
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
  RotateCw,
} from 'lucide-react';
import { ActionMenu } from '@/components/common/action-menu';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import { CustomFields } from '@/components/common/custom-fields';
import {
  useContactsPageQuery,
  useCreateContactMutation,
  useUpdateContactMutation,
  useDeleteContactMutation,
  useStarContactMutation,
  useUnstarContactMutation,
  useMergeContactsMutation,
  useBulkDeleteContactsMutation,
  useImportContactsCsvMutation,
  exportContactsCsvApi,
  ContactItem,
} from '@/lib/api/contacts';
import { useUsersQuery } from '@/lib/api/users';
import { useCompaniesQuery } from '@/lib/api/companies';
import { SearchableCompanySelect } from '@/components/common/searchable-company-select';
import { PageTabs } from '@/components/common/page-tabs';
import { useEntityCustomFieldsQuery, type CustomFieldValue } from '@/lib/api/custom-fields';
import { updateContactDirectoryParams } from '@/components/features/contacts/contact-directory-params';

const UNSUPPORTED_CONTACT_ACTIONS_AVAILABLE = false;

export default function ContactsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const directoryParamsRef = useRef(queryString);
  const activeTab = searchParams.get('view') === 'starred' ? 'starred' : 'all';
  const requestedPage = Number.parseInt(searchParams.get('page') ?? '1', 10);
  const page = Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const companyFilter = searchParams.get('company') ?? '';
  const ownerFilter = searchParams.get('owner') ?? '';
  const urlSearchTerm = searchParams.get('search') ?? '';
  const [searchTerm, setSearchTerm] = useState(urlSearchTerm);
  const limit = 15;

  const updateDirectoryUrl = useCallback((changes: Record<string, string | null>) => {
    const nextQuery = updateContactDirectoryParams(directoryParamsRef.current, changes);
    directoryParamsRef.current = nextQuery;
    router.replace(nextQuery ? `${pathname}?${nextQuery}` : pathname, { scroll: false });
  }, [pathname, router]);

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
  const [formCustomFields, setFormCustomFields] = useState<Record<string, CustomFieldValue>>({});

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
    setFormCustomFields({});
  };

  useEffect(() => {
    directoryParamsRef.current = queryString;
  }, [queryString]);

  useEffect(() => {
    const handler = window.setTimeout(() => setSearchTerm(urlSearchTerm), 0);
    return () => window.clearTimeout(handler);
  }, [urlSearchTerm]);

  useEffect(() => {
    if (searchTerm === urlSearchTerm) return;
    const handler = setTimeout(() => {
      updateDirectoryUrl({ search: searchTerm.trim() || null, page: null });
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm, updateDirectoryUrl, urlSearchTerm]);

  // Queries
  const {
    data: contactsPage,
    isLoading: isContactsLoading,
    isFetching: isContactsFetching,
    isError: isContactsError,
    refetch: refetchAll,
  } = useContactsPageQuery(
    {
      page,
      limit,
      search: urlSearchTerm,
      companyId: companyFilter || undefined,
      ownerId: ownerFilter || undefined,
      isStarred: activeTab === 'starred' ? true : undefined,
    },
  );
  const allContacts = contactsPage?.items ?? [];
  const { data: companiesList = [] } = useCompaniesQuery(1, 100);
  const { data: usersList = [] } = useUsersQuery(1, 100);
  const {
    data: customFields = [],
    isLoading: isCustomFieldsLoading,
    isError: isCustomFieldsError,
  } = useEntityCustomFieldsQuery('Contact', isCreateModalOpen || isEditModalOpen);

  const contacts = allContacts;
  const totalContacts = contactsPage?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(totalContacts / limit));

  useEffect(() => {
    if (!isContactsLoading && contactsPage && page > pageCount) {
      updateDirectoryUrl({ page: String(pageCount) });
    }
  }, [contactsPage, isContactsLoading, page, pageCount, updateDirectoryUrl]);

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
    const displayName = (formName || `${formFirstName} ${formLastName}`).trim();
    const emailVal = formEmail.trim();
    if (!displayName || !emailVal) {
      setErrorMessage('Contact name and email are required.');
      return;
    }
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
        custom_fields: formCustomFields,
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
    const displayName = (formName || `${formFirstName} ${formLastName}`).trim();
    const email = formEmail.trim();
    if (!displayName || !email) {
      setErrorMessage('Contact name and email are required.');
      return;
    }
    try {
      setErrorMessage(null);
      await updateContactMutation.mutateAsync({
        id: contactToEdit.id,
        data: {
          first_name: formFirstName || undefined,
          last_name: formLastName || undefined,
          name: displayName,
          email,
          phone: formPhone || undefined,
          company_id: formCompanyId || undefined,
          position: formPosition || undefined,
          job_title: formJobTitle || formPosition || undefined,
          custom_fields: formCustomFields,
          expected_updated_at: contactToEdit.updated_at,
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
    setFormCustomFields(item.custom_fields ?? {});
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
      className: 'w-12 text-center',
      cell: (item) => (
        <button
          type="button"
          disabled={starContactMutation.isPending || unstarContactMutation.isPending}
          onClick={(e) => {
            e.stopPropagation();
            void handleToggleStar(item);
          }}
          className="mx-auto flex size-9 items-center justify-center rounded-md text-slate-400 transition hover:bg-amber-50 hover:text-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label={item.is_starred ? `Unstar ${item.name}` : `Star ${item.name}`}
        >
          <Star className={item.is_starred ? 'size-3.5 fill-amber-400 text-amber-500' : 'size-3.5'} />
        </button>
      ),
    },
    {
      id: 'name',
      header: 'Name',
      cell: (item) => (
        <div className="flex min-w-40 items-center gap-2.5">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-blue-100 text-[10px] font-semibold text-blue-700">
            {item.name ? item.name.charAt(0).toUpperCase() : 'C'}
          </div>
          <div className="min-w-0">
            <Link
              href={`/contacts/${item.id}`}
              className="block truncate text-xs font-semibold text-slate-900 hover:text-blue-600 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              {item.name}
            </Link>
          </div>
        </div>
      ),
    },
    {
      id: 'email',
      header: 'Email Address',
      cell: (item) => (
        <span className="block max-w-52 truncate text-xs text-slate-600">{item.email || '—'}</span>
      ),
    },
    {
      id: 'phone',
      header: 'Phone Number',
      cell: (item) => (
        <span className="text-xs text-slate-600">{item.phone || '—'}</span>
      ),
    },
    {
      id: 'position',
      header: 'Job Title',
      enableHiding: true,
      cell: (item) => (
        <span className="inline-flex items-center gap-2 text-xs text-slate-700">
          <span className="size-1.5 rounded-full bg-blue-500" aria-hidden="true" />
          {item.position || 'Not specified'}
        </span>
      ),
    },
    {
      id: 'company',
      header: 'Company',
      cell: (item) => (
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700">
          <Building className="size-3.5 shrink-0 text-slate-400" aria-hidden="true" />
          {item.company_name || 'Unassociated'}
        </span>
      ),
    },
    {
      id: 'owner',
      header: 'Contact Owner',
      enableHiding: true,
      cell: (item) => (
        <span className="text-xs text-slate-600">{item.owner_name || 'Unassigned'}</span>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      enableHiding: true,
      cell: (item) => (
        <Badge
          variant="outline"
          className={item.is_starred
            ? 'border-amber-200 bg-amber-50 text-[10px] font-medium text-amber-700'
            : 'border-emerald-200 bg-emerald-50 text-[10px] font-medium text-emerald-700'}
        >
          {item.is_starred ? 'Starred' : 'Active'}
        </Badge>
      ),
    },
  ];

  return (
    <div className="mx-auto w-full max-w-[1600px] space-y-3 pb-8">
      <h1 className="sr-only">Contacts</h1>

      <div className="flex flex-col gap-3 border-b border-slate-200 pb-2 lg:flex-row lg:items-center lg:justify-between">
        <PageTabs
          value={activeTab}
          onValueChange={(tab) => {
            updateDirectoryUrl({ view: tab === 'all' ? null : tab, page: null });
            setSelectedIds(new Set());
          }}
          tabs={[
            { value: 'all', icon: <User className="size-3.5" />, label: 'All Contacts' },
            { value: 'starred', icon: <Star className="size-3.5" />, label: 'Starred' },
          ]}
          className="min-w-0 lg:flex-1"
          listClassName="border-0"
          triggerClassName="h-9 px-3 text-xs font-medium"
        />

        <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
          <Button size="sm" variant="outline" className="h-9" onClick={() => void refetchAll()} disabled={isContactsFetching}>
            <RotateCw className={isContactsFetching ? 'size-3.5 animate-spin' : 'size-3.5'} aria-hidden="true" />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <PermissionGate permission={PERMISSIONS.CONTACTS.CREATE}>
            <Button
              size="sm"
              onClick={() => {
                resetForm();
                setIsCreateModalOpen(true);
              }}
              className="h-9 gap-1.5 bg-slate-950 text-xs font-semibold text-white hover:bg-slate-800"
            >
              <Plus className="size-3.5" aria-hidden="true" />
              <span>Create Contact</span>
            </Button>
          </PermissionGate>

          {UNSUPPORTED_CONTACT_ACTIONS_AVAILABLE && <ActionMenu
            label="More"
            className="h-8 text-xs font-semibold"
            actions={[
              {
                label: 'Export CSV (Not available)',
                permission: PERMISSIONS.CONTACTS.EXPORT,
                icon: <FileSpreadsheet className="w-4 h-4 text-emerald-600" />,
                disabled: true,
                onSelect: handleExportCsv,
              },
              {
                label: 'Import CSV (Not available)',
                permission: PERMISSIONS.CONTACTS.IMPORT,
                icon: <Upload className="w-4 h-4 text-blue-600" />,
                disabled: true,
                onSelect: handleImportCsv,
              },
              {
                label: 'Merge contacts (Not available)',
                permission: PERMISSIONS.CONTACTS.UPDATE,
                icon: <GitMerge className="w-4 h-4 text-purple-600" />,
                disabled: true,
                onSelect: () => setIsMergeModalOpen(true),
              },
            ]}
          />}

          {selectedIds.size > 0 && (
            <PermissionGate permission={PERMISSIONS.CONTACTS.BULK_DELETE}>
              <Button
                size="sm"
                variant="outline"
                onClick={handleBulkDelete}
                className="h-9 gap-1 border-rose-300 text-xs font-semibold text-rose-600 hover:bg-rose-50"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Delete Selected ({selectedIds.size})</span>
              </Button>
            </PermissionGate>
          )}
        </div>
      </div>

      {successMessage && (
        <div role="status" className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-900">
          <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />
          <span>{successMessage}</span>
          <button type="button" onClick={() => setSuccessMessage(null)} className="ml-auto rounded px-2 py-1 hover:bg-emerald-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500">Dismiss</button>
        </div>
      )}
      {errorMessage && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-900">
          <AlertCircle className="size-4 shrink-0 text-rose-600" />
          <span>{errorMessage}</span>
          <button type="button" onClick={() => setErrorMessage(null)} className="ml-auto rounded px-2 py-1 hover:bg-rose-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500">Dismiss</button>
        </div>
      )}
      {isContactsError && (
        <div role="alert" className="flex flex-wrap items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-900">
          <AlertCircle className="size-4 shrink-0 text-rose-600" />
          <span>Contacts could not be loaded. Please try again.</span>
          <Button size="sm" variant="outline" className="ml-auto h-8" onClick={() => void refetchAll()}>Try again</Button>
        </div>
      )}

      <DataTable
        columns={columns}
        data={contacts}
        getRowKey={(item) => item.id}
        onRowClick={(item) => router.push(`/contacts/${item.id}`)}
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search name, phone, email, or job title..."
        filters={[
          {
            label: companyFilter
              ? `Company: ${companiesList.find((company) => company.id === companyFilter)?.name ?? 'Selected'}`
              : 'Company',
            value: 'company',
            options: [
              { label: 'All companies', value: '' },
              ...companiesList.map((company) => ({ label: company.name, value: company.id })),
            ],
            onChange: (value) => {
              updateDirectoryUrl({ company: value || null, page: null });
              setSelectedIds(new Set());
            },
          },
          {
            label: ownerFilter
              ? `Owner: ${usersList.find((user) => user.id === ownerFilter)?.name ?? 'Selected'}`
              : 'Owner',
            value: 'owner',
            options: [
              { label: 'All owners', value: '' },
              ...usersList.map((user) => ({ label: user.name, value: user.id })),
            ],
            onChange: (value) => {
              updateDirectoryUrl({ owner: value || null, page: null });
              setSelectedIds(new Set());
            },
          },
        ]}
        hasActiveFilters={Boolean(searchTerm || companyFilter || ownerFilter)}
        onClearFilters={() => {
          setSearchTerm('');
          updateDirectoryUrl({ search: null, company: null, owner: null, page: null });
          setSelectedIds(new Set());
        }}
        actionVariant="menu"
        actions={(item) => [
          {
            label: 'Edit',
            permission: PERMISSIONS.CONTACTS.UPDATE,
            icon: <Edit className="w-4 h-4 text-blue-600 mr-2" />,
            onClick: () => openEditModal(item),
          },
          {
            label: 'Delete',
            variant: 'destructive',
            permission: PERMISSIONS.CONTACTS.DELETE,
            icon: <Trash2 className="w-4 h-4 text-rose-600 mr-2" />,
            onClick: () => setContactToDelete(item),
          },
        ]}
        emptyTitle="No contacts found"
        emptyDescription={searchTerm || companyFilter || ownerFilter || activeTab === 'starred'
          ? 'Try changing your search, filters, or contact view.'
          : 'Create your first contact to start building your customer directory.'}
        showCheckbox
        getSelectionLabel={(item) => `Select ${item.name}`}
        selectedIds={selectedIds}
        onToggleAllRows={(checked) => {
          if (checked) {
            setSelectedIds(new Set(contacts.map((c) => c.id)));
          } else {
            setSelectedIds(new Set());
          }
        }}
        onToggleRow={(item, checked) => {
          const next = new Set(selectedIds);
          if (checked) next.add(item.id);
          else next.delete(item.id);
          setSelectedIds(next);
        }}
        pagination={{
          pageIndex: page - 1,
          pageCount,
          onPageChange: (pIndex) => {
            updateDirectoryUrl({ page: String(pIndex + 1) });
            setSelectedIds(new Set());
          },
          totalRecords: totalContacts,
        }}
        isLoading={isContactsLoading}
        loadingLabel="Loading contacts"
        className="overflow-hidden rounded-lg shadow-none"
        tableClassName="min-w-[980px]"
      />

      {/* CREATE CONTACT MODAL */}
      <ModalShell
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title={
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
            <User className="w-5 h-5 text-blue-600" />
            <span>Create New Contact</span>
          </h3>
        }
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="contact-create-first-name" className="font-semibold text-slate-700">First Name</Label>
              <Input
                id="contact-create-first-name"
                type="text"
                placeholder="e.g. selva"
                value={formFirstName}
                onChange={(e) => setFormFirstName(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="contact-create-last-name" className="font-semibold text-slate-700">Last Name</Label>
              <Input
                id="contact-create-last-name"
                type="text"
                placeholder="e.g. kumar"
                value={formLastName}
                onChange={(e) => setFormLastName(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="contact-create-full-name" className="font-semibold text-slate-700">Full Name</Label>
            <Input
              id="contact-create-full-name"
              type="text"
              placeholder="e.g. selvakumar"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              className="h-9 text-xs"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="contact-create-email" className="font-semibold text-slate-700">Email Address</Label>
              <Input
                id="contact-create-email"
                type="email"
                required
                placeholder="user@example.com"
                value={formEmail}
                onChange={(e) => setFormEmail(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="contact-create-phone" className="font-semibold text-slate-700">Phone Number</Label>
              <Input
                id="contact-create-phone"
                type="text"
                placeholder="7374837284"
                value={formPhone}
                onChange={(e) => setFormPhone(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="contact-create-company" className="font-semibold text-slate-700">Company</Label>
            <SearchableCompanySelect
              id="contact-create-company"
              ariaLabel="Select company for new contact"
              value={formCompanyId}
              onChange={setFormCompanyId}
              companies={companiesList}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="contact-create-position" className="font-semibold text-slate-700">Position</Label>
              <Input
                id="contact-create-position"
                type="text"
                placeholder="e.g. frontend"
                value={formPosition}
                onChange={(e) => setFormPosition(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="contact-create-job-title" className="font-semibold text-slate-700">Job Title</Label>
              <Input
                id="contact-create-job-title"
                type="text"
                placeholder="e.g. software"
                value={formJobTitle}
                onChange={(e) => setFormJobTitle(e.target.value)}
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
            idPrefix="contact-create"
          />

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsCreateModalOpen(false)} className="cursor-pointer">
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={createContactMutation.isPending} className="bg-blue-600 text-white font-semibold cursor-pointer">
              {createContactMutation.isPending ? 'Creating...' : 'Create Contact'}
            </Button>
          </div>
        </form>
      </ModalShell>

      {/* EDIT CONTACT MODAL */}
      <ModalShell
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        title={
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
            <Edit className="w-5 h-5 text-blue-600" />
            <span>Edit Contact Profile</span>
          </h3>
        }
      >
        <form onSubmit={handleEditSubmit} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="contact-edit-first-name" className="font-semibold text-slate-700">First Name</Label>
              <Input
                id="contact-edit-first-name"
                type="text"
                value={formFirstName}
                onChange={(e) => setFormFirstName(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="contact-edit-last-name" className="font-semibold text-slate-700">Last Name</Label>
              <Input
                id="contact-edit-last-name"
                type="text"
                value={formLastName}
                onChange={(e) => setFormLastName(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="contact-edit-full-name" className="font-semibold text-slate-700">Full Name</Label>
            <Input
              id="contact-edit-full-name"
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              className="h-9 text-xs"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="contact-edit-email" className="font-semibold text-slate-700">Email Address</Label>
              <Input
                id="contact-edit-email"
                type="email"
                required
                value={formEmail}
                onChange={(e) => setFormEmail(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="contact-edit-phone" className="font-semibold text-slate-700">Phone Number</Label>
              <Input
                id="contact-edit-phone"
                type="text"
                value={formPhone}
                onChange={(e) => setFormPhone(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="contact-edit-company" className="font-semibold text-slate-700">Company</Label>
            <SearchableCompanySelect
              id="contact-edit-company"
              ariaLabel="Select company for contact"
              value={formCompanyId}
              onChange={setFormCompanyId}
              companies={companiesList}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="contact-edit-position" className="font-semibold text-slate-700">Position</Label>
              <Input
                id="contact-edit-position"
                type="text"
                value={formPosition}
                onChange={(e) => setFormPosition(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="contact-edit-job-title" className="font-semibold text-slate-700">Job Title</Label>
              <Input
                id="contact-edit-job-title"
                type="text"
                value={formJobTitle}
                onChange={(e) => setFormJobTitle(e.target.value)}
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
            idPrefix="contact-edit"
          />

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

      {/* MERGE CONTACTS MODAL */}
      <ModalShell
        isOpen={isMergeModalOpen}
        onClose={() => setIsMergeModalOpen(false)}
        title={
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
            <GitMerge className="w-5 h-5 text-purple-600" />
            <span>Merge Contact Profiles</span>
          </h3>
        }
      >
        <form onSubmit={handleMergeSubmit} className="space-y-4 text-xs">
          <div className="space-y-1">
            <Label className="font-semibold text-slate-700">Primary Contact (To Keep)</Label>
            <ResponsiveSelect
              value={primaryContactId}
              onValueChange={setPrimaryContactId}
              className="w-full h-9 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-900"
            >
              <option value="">Select primary contact...</option>
              {allContacts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.email})
                </option>
              ))}
            </ResponsiveSelect>
          </div>

          <div className="space-y-1">
            <Label className="font-semibold text-slate-700">Secondary Contact (To Merge &amp; Remove)</Label>
            <ResponsiveSelect
              value={secondaryContactId}
              onValueChange={setSecondaryContactId}
              className="w-full h-9 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-900"
            >
              <option value="">Select secondary contact...</option>
              {allContacts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.email})
                </option>
              ))}
            </ResponsiveSelect>
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsMergeModalOpen(false)} className="cursor-pointer">
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={mergeContactsMutation.isPending} className="bg-purple-600 hover:bg-purple-700 text-white font-semibold cursor-pointer">
              {mergeContactsMutation.isPending ? 'Merging...' : 'Merge Profiles'}
            </Button>
          </div>
        </form>
      </ModalShell>

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
