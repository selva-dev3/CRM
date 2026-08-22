'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Building2,
  Globe,
  Users,
  Briefcase,
  Plus,
  FileSpreadsheet,
  Upload,
  Search,
  Trash2,
  Edit,
  CheckCircle2,
  AlertCircle,
  X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import { ConfirmModal } from '@/components/common/confirm-modal';
import {
  useCompaniesQuery,
  useCreateCompanyMutation,
  useUpdateCompanyMutation,
  useDeleteCompanyMutation,
  useBulkDeleteCompaniesMutation,
  useImportCompaniesCsvMutation,
  exportCompaniesCsvApi,
  lookupCompanyDomainApi,
  CompanyItem
} from '@/lib/api/companies';

export default function CompaniesPage() {
  const router = useRouter();
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
  const [companyToEdit, setCompanyToEdit] = useState<CompanyItem | null>(null);
  const [companyToDelete, setCompanyToDelete] = useState<CompanyItem | null>(null);

  // Form State matching exact payload schema: name, domain, website, industry, size, employee_count
  const [formName, setFormName] = useState('');
  const [formDomain, setFormDomain] = useState('');
  const [formWebsite, setFormWebsite] = useState('');
  const [formIndustry, setFormIndustry] = useState('');
  const [formSize, setFormSize] = useState('');
  const [formEmployeeCount, setFormEmployeeCount] = useState<number | ''>('');

  // Search Debounce
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Queries
  const { data: companies = [], isLoading, refetch } = useCompaniesQuery(page, limit, debouncedSearchTerm);

  // Mutations
  const createCompanyMutation = useCreateCompanyMutation();
  const updateCompanyMutation = useUpdateCompanyMutation();
  const deleteCompanyMutation = useDeleteCompanyMutation();
  const bulkDeleteMutation = useBulkDeleteCompaniesMutation();
  const importCsvMutation = useImportCompaniesCsvMutation();

  const resetForm = () => {
    setFormName('');
    setFormDomain('');
    setFormWebsite('');
    setFormIndustry('');
    setFormSize('');
    setFormEmployeeCount('');
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName) {
      setErrorMessage('Please provide company name.');
      return;
    }
    try {
      setErrorMessage(null);
      await createCompanyMutation.mutateAsync({
        name: formName,
        domain: formDomain || undefined,
        website: formWebsite || undefined,
        industry: formIndustry || undefined,
        size: formSize || (formEmployeeCount ? String(formEmployeeCount) : undefined),
        employee_count: formEmployeeCount !== '' ? Number(formEmployeeCount) : undefined,
      });
      setSuccessMessage(`Company '${formName}' created successfully.`);
      setIsCreateModalOpen(false);
      resetForm();
      refetch();
    } catch {
      setErrorMessage('Failed to create company profile.');
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyToEdit) return;
    try {
      setErrorMessage(null);
      await updateCompanyMutation.mutateAsync({
        id: companyToEdit.id,
        data: {
          name: formName,
          domain: formDomain || undefined,
          website: formWebsite || undefined,
          industry: formIndustry || undefined,
          size: formSize || (formEmployeeCount ? String(formEmployeeCount) : undefined),
          employee_count: formEmployeeCount !== '' ? Number(formEmployeeCount) : undefined,
        },
      });
      setSuccessMessage(`Company '${formName}' updated successfully.`);
      setIsEditModalOpen(false);
      setCompanyToEdit(null);
      resetForm();
      refetch();
    } catch {
      setErrorMessage('Failed to update company profile.');
    }
  };

  const openEditModal = (item: CompanyItem) => {
    setCompanyToEdit(item);
    setFormName(item.name);
    setFormDomain(item.domain || '');
    setFormWebsite(item.website || '');
    setFormIndustry(item.industry || '');
    setFormSize(item.size || '');
    setFormEmployeeCount(item.employee_count ?? '');
    setIsEditModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!companyToDelete) return;
    try {
      setErrorMessage(null);
      await deleteCompanyMutation.mutateAsync(companyToDelete.id);
      setSuccessMessage(`Company '${companyToDelete.name}' deleted successfully.`);
      setCompanyToDelete(null);
      refetch();
    } catch {
      setErrorMessage('Failed to delete company profile.');
      setCompanyToDelete(null);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    if (confirm(`Are you sure you want to delete ${selectedIds.size} selected company profile(s)?`)) {
      try {
        setErrorMessage(null);
        const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
        setSuccessMessage(res.message || `${selectedIds.size} companies deleted successfully.`);
        setSelectedIds(new Set());
        refetch();
      } catch {
        setErrorMessage('Failed to bulk delete companies.');
      }
    }
  };

  const handleExportCsv = async () => {
    try {
      setErrorMessage(null);
      const res = await exportCompaniesCsvApi();
      setSuccessMessage(`Companies CSV exported. Download URL: ${res.download_url}`);
    } catch {
      setErrorMessage('Failed to export companies CSV.');
    }
  };

  const handleImportCsv = async () => {
    try {
      setErrorMessage(null);
      const res = await importCsvMutation.mutateAsync();
      setSuccessMessage(res.message || 'Companies imported from CSV successfully.');
      refetch();
    } catch {
      setErrorMessage('Failed to import companies CSV.');
    }
  };

  const handleDomainLookup = async () => {
    if (!formDomain && !formWebsite) return;
    const searchTarget = formDomain || formWebsite;
    try {
      setErrorMessage(null);
      const res = await lookupCompanyDomainApi(searchTarget);
      if (res.name) setFormName(res.name);
      if (res.industry) setFormIndustry(res.industry);
      if (res.employee_count) setFormEmployeeCount(res.employee_count);
      setSuccessMessage(`Enriched company profile for domain '${searchTarget}'.`);
    } catch {
      setErrorMessage('Domain lookup failed.');
    }
  };

  const columns: DataTableColumn<CompanyItem>[] = [
    {
      id: 'name',
      header: 'Company Name',
      cell: (item) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-700 font-bold text-xs shrink-0">
            <Building2 className="w-4 h-4" />
          </div>
          <div>
            <Link href={`/companies/${item.id}`} className="font-bold text-slate-900 text-xs hover:text-blue-600 hover:underline">
              {item.name}
            </Link>
            <div className="text-[11px] text-slate-500">{item.domain || item.website || 'N/A'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'industry',
      header: 'Industry Sector',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-semibold">
          <Briefcase className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <span>{item.industry || 'General Business'}</span>
        </div>
      ),
    },
    {
      id: 'website',
      header: 'Website Domain',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-blue-600 text-xs font-semibold">
          <Globe className="w-3.5 h-3.5 text-blue-400 shrink-0" />
          {item.website ? (
            <a href={item.website.startsWith('http') ? item.website : `https://${item.website}`} target="_blank" rel="noreferrer" className="hover:underline">
              {item.website}
            </a>
          ) : (
            <span className="text-slate-400">N/A</span>
          )}
        </div>
      ),
    },
    {
      id: 'employee_count',
      header: 'Company Size',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-semibold">
          <Users className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <span>{item.employee_count ? `${item.employee_count} employees` : item.size ? `${item.size} staff` : 'Enterprise'}</span>
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
            <Building2 className="w-6 h-6 text-blue-600" />
            <span>Company Management</span>
          </h1>
          <p className="text-xs font-medium text-slate-500 mt-1">
            Manage organization accounts, domain lookups, company size metrics, and bulk operations.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <PermissionGate permission={PERMISSIONS.COMPANIES.CREATE}>
            <Button
              size="sm"
              onClick={() => {
                resetForm();
                setIsCreateModalOpen(true);
              }}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs gap-1.5 cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Add Company</span>
            </Button>
          </PermissionGate>

          <PermissionGate permission={PERMISSIONS.COMPANIES.EXPORT}>
            <Button
              size="sm"
              variant="outline"
              onClick={handleExportCsv}
              className="border-slate-300 font-semibold text-xs gap-1 cursor-pointer"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
              <span>Export CSV</span>
            </Button>
          </PermissionGate>

          <PermissionGate permission={PERMISSIONS.COMPANIES.IMPORT}>
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
          </PermissionGate>

          {selectedIds.size > 0 && (
            <PermissionGate permission={PERMISSIONS.COMPANIES.BULK_DELETE}>
              <Button
                size="sm"
                variant="outline"
                onClick={handleBulkDelete}
                className="border-rose-300 text-rose-600 hover:bg-rose-50 font-semibold text-xs gap-1 cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Delete Selected ({selectedIds.size})</span>
              </Button>
            </PermissionGate>
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

      {/* Companies DataTable */}
      <DataTable
        columns={columns as any}
        data={companies as any}
        getRowKey={(item: any) => item.id}
        onRowClick={(item: any) => router.push(`/companies/${item.id}`)}
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search companies by name or domain..."
        actionVariant="menu"
        actions={(item: any) => [
          {
            label: 'Edit',
            permission: PERMISSIONS.COMPANIES.UPDATE,
            icon: <Edit className="w-4 h-4 text-blue-600 mr-2" />,
            onClick: () => openEditModal(item),
          },
          {
            label: 'Delete',
            variant: 'destructive',
            permission: PERMISSIONS.COMPANIES.DELETE,
            icon: <Trash2 className="w-4 h-4 text-rose-600 mr-2" />,
            onClick: () => setCompanyToDelete(item),
          },
        ]}
        emptyTitle="No companies found"
        emptyDescription="Create your first company profile or import CSV data."
        showCheckbox
        selectedIds={selectedIds}
        onToggleAllRows={(checked) => {
          if (checked) {
            setSelectedIds(new Set(companies.map((c) => c.id)));
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
          pageCount: Math.ceil((companies.length || 1) / limit) || 1,
          onPageChange: (pIndex) => setPage(pIndex + 1),
          totalRecords: companies.length,
        }}
      />

      {/* CREATE COMPANY MODAL (Payload fields: name, domain, website, industry, size, employee_count) */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-md bg-white rounded-2xl border border-slate-300 shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <Building2 className="w-5 h-5 text-blue-600" />
                <span>Create New Company</span>
              </h3>
              <button type="button" onClick={() => setIsCreateModalOpen(false)} className="text-slate-400 hover:text-slate-700 cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Company Name</Label>
                <Input
                  type="text"
                  placeholder="e.g. selvakumar / Acme Corp"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Domain Handle</Label>
                  <Input
                    type="text"
                    placeholder="e.g. linkedin"
                    value={formDomain}
                    onChange={(e) => setFormDomain(e.target.value)}
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Website URL</Label>
                  <div className="flex items-center gap-1">
                    <Input
                      type="text"
                      placeholder="https://crm-one-sable.vercel.app/"
                      value={formWebsite}
                      onChange={(e) => setFormWebsite(e.target.value)}
                      className="h-9 text-xs"
                    />
                    <button
                      type="button"
                      onClick={handleDomainLookup}
                      title="Enrich domain info"
                      className="px-2 py-2 text-[10px] bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded cursor-pointer shrink-0"
                    >
                      Enrich
                    </button>
                  </div>
                </div>
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Industry Sector</Label>
                <Input
                  type="text"
                  placeholder="e.g. software / IT"
                  value={formIndustry}
                  onChange={(e) => setFormIndustry(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Size String</Label>
                  <Input
                    type="text"
                    placeholder='e.g. "10"'
                    value={formSize}
                    onChange={(e) => setFormSize(e.target.value)}
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Employee Count</Label>
                  <Input
                    type="number"
                    placeholder="10"
                    value={formEmployeeCount}
                    onChange={(e) => setFormEmployeeCount(e.target.value !== '' ? Number(e.target.value) : '')}
                    className="h-9 text-xs"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setIsCreateModalOpen(false)} className="cursor-pointer">
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={createCompanyMutation.isPending} className="bg-blue-600 text-white font-semibold cursor-pointer">
                  {createCompanyMutation.isPending ? 'Creating...' : 'Create Company'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT COMPANY MODAL */}
      {isEditModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-md bg-white rounded-2xl border border-slate-300 shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <Edit className="w-5 h-5 text-blue-600" />
                <span>Edit Company Profile</span>
              </h3>
              <button type="button" onClick={() => setIsEditModalOpen(false)} className="text-slate-400 hover:text-slate-700 cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

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

              <div className="grid grid-cols-2 gap-3">
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

              <div className="grid grid-cols-2 gap-3">
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

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setIsEditModalOpen(false)} className="cursor-pointer">
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={updateCompanyMutation.isPending} className="bg-blue-600 text-white font-semibold cursor-pointer">
                  {updateCompanyMutation.isPending ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CONFIRM DELETE MODAL */}
      <ConfirmModal
        isOpen={!!companyToDelete}
        onClose={() => setCompanyToDelete(null)}
        onConfirm={handleConfirmDelete}
        title="Delete Company Profile"
        description="This action cannot be undone."
        confirmText="Delete Company"
        variant="danger"
        isLoading={deleteCompanyMutation.isPending}
        message={
          companyToDelete && (
            <p>
              Are you sure you want to delete company <strong className="text-slate-900">{companyToDelete.name}</strong> ({companyToDelete.website || companyToDelete.domain || 'No website'})?
            </p>
          )
        }
      />
    </div>
  );
}
