'use client';

import React, { useState, useMemo } from 'react';
import { 
  Plus, 
  Building2, 
  Mail, 
  Phone, 
  X, 
  Loader2, 
  CheckCircle2, 
  AlertCircle,
  Sparkles,
  RefreshCw
} from 'lucide-react';
import { Button, Card, Label, Input, Badge, Alert, AlertDescription } from '@/components/ui';
import { DataTable, DataTableColumn, TableActionOption } from '@/components/shared/data-table';
import { useLeadsQuery, useCreateLeadMutation, Lead } from '@/lib/api/leads';
import { useOrganizationsQuery } from '@/lib/api/organizations';
import { useCompaniesQuery } from '@/lib/api/companies';

export default function LeadsPage() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  
  // Form State
  const [contactName, setContactName] = useState('');
  const [company, setCompany] = useState('');
  const [customCompany, setCustomCompany] = useState('');
  const [title, setTitle] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [status, setStatus] = useState('New');
  const [source, setSource] = useState('Website');
  const [organizationId, setOrganizationId] = useState('');

  // Feedback Banner State
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // TanStack Query Hooks for Leads, Organizations, & Companies API
  const { data: leads = [], isLoading, isError, refetch } = useLeadsQuery({
    search: searchTerm || undefined,
    status: statusFilter || undefined,
  });

  const { data: organizations = [], isLoading: isOrgsLoading } = useOrganizationsQuery();
  const { data: companies = [], isLoading: isCompaniesLoading } = useCompaniesQuery();

  const createLeadMutation = useCreateLeadMutation();

  const resetForm = () => {
    setContactName('');
    setCompany(companies.length > 0 ? companies[0].name : '');
    setCustomCompany('');
    setTitle('');
    setEmail('');
    setPhone('');
    setStatus('New');
    setSource('Website');
    setOrganizationId(organizations.length > 0 ? organizations[0].id : 'org-1');
    setErrorMessage(null);
  };

  const handleOpenModal = () => {
    resetForm();
    if (organizations.length > 0) setOrganizationId(organizations[0].id);
    if (companies.length > 0) setCompany(companies[0].name);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    if (createLeadMutation.isPending) return;
    setIsModalOpen(false);
    resetForm();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    const finalCompany = company === 'other' ? customCompany.trim() : company.trim();

    if (!contactName.trim() || !email.trim()) {
      setErrorMessage('Contact Name and Email are required.');
      return;
    }

    if (!finalCompany) {
      setErrorMessage('Company Name is required.');
      return;
    }

    try {
      const payload = {
        contact_name: contactName.trim(),
        company: finalCompany,
        title: title.trim() || `${contactName.trim()} Opportunity`,
        email: email.trim(),
        phone: phone.trim() || undefined,
        status,
        source,
        organization_id: organizationId || (organizations[0]?.id ?? 'org-1'),
      };

      await createLeadMutation.mutateAsync(payload);
      
      setSuccessMessage(`Lead for "${contactName}" created successfully!`);
      setIsModalOpen(false);
      resetForm();

      setTimeout(() => {
        setSuccessMessage(null);
      }, 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to create lead. Please check API server.');
    }
  };

  // Define Columns for Reusable DataTable
  const columns: DataTableColumn<Lead>[] = useMemo(
    () => [
      {
        id: 'name',
        header: 'Name & Title',
        cell: (item: Lead) => (
          <div>
            <span className="block text-xs font-black text-slate-900">{item.contact_name}</span>
            <span className="text-[11px] font-semibold text-slate-500">{item.title}</span>
          </div>
        ),
      },
      {
        id: 'company',
        header: 'Company',
        cell: (item: Lead) => (
          <div className="flex items-center gap-1.5 font-bold text-xs text-slate-900">
            <Building2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            <span>{item.company}</span>
          </div>
        ),
      },
      {
        id: 'contact',
        header: 'Email / Phone',
        cell: (item: Lead) => (
          <div className="text-xs font-bold text-slate-900 space-y-0.5">
            <div className="flex items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
              <span>{item.email}</span>
            </div>
            {item.phone && (
              <div className="flex items-center gap-1.5 text-slate-500 text-[11px]">
                <Phone className="w-3 h-3 shrink-0" />
                <span>{item.phone}</span>
              </div>
            )}
          </div>
        ),
      },
      {
        id: 'source',
        header: 'Source',
        cell: (item: Lead) => (
          <span className="text-xs font-bold text-slate-800">{item.source}</span>
        ),
      },
      {
        id: 'status',
        header: 'Status',
        cell: (item: Lead) => (
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-black border ${
            item.status === 'New' ? 'bg-blue-50 text-blue-800 border-blue-200' :
            item.status === 'Qualified' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' :
            item.status === 'Contacted' ? 'bg-amber-50 text-amber-800 border-amber-200' :
            'bg-slate-100 text-slate-800 border-slate-200'
          }`}>
            <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5" />
            {item.status}
          </span>
        ),
      },
      {
        id: 'score',
        header: 'AI Score',
        className: 'text-right',
        cell: (item: Lead) => (
          <div className="text-right">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-purple-50 text-purple-800 border border-purple-200 text-[11px] font-black">
              <Sparkles className="w-3 h-3 text-purple-600" />
              {item.score ?? 75}/100
            </span>
          </div>
        ),
      },
    ],
    []
  );

  // Define Row Actions for DataTable
  const actions: TableActionOption<Lead>[] = [
    {
      label: 'Edit Lead',
      onClick: (lead) => alert(`Edit lead: ${lead.contact_name}`),
    },
    {
      label: 'Delete Lead',
      variant: 'destructive',
      onClick: (lead) => alert(`Delete lead: ${lead.contact_name}`),
    },
  ];

  return (
    <div className="space-y-6 text-black">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black text-black tracking-tight">
            Lead Management
          </h1>
          <p className="text-sm font-bold text-slate-800 mt-1">
            Capture, track, and score sales leads with AI
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            onClick={handleOpenModal}
            size="sm"
            className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold shadow-sm cursor-pointer px-4 py-2 text-sm"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            + Add New Lead
          </Button>
        </div>
      </div>

      {/* Success Notification Alert */}
      {successMessage && (
        <Alert variant="default" className="bg-emerald-50 border-emerald-300 text-emerald-950 font-bold">
          <CheckCircle2 className="h-4 w-4 text-emerald-600 mr-2" />
          <AlertDescription className="text-emerald-900 font-bold">
            {successMessage}
          </AlertDescription>
        </Alert>
      )}

      {/* Reusable Enterprise DataTable Component */}
      <DataTable<Lead>
        columns={columns}
        data={leads}
        getRowKey={(item) => item.id}
        emptyTitle="No leads found"
        emptyDescription="Click '+ Add New Lead' above to create your first sales lead."
        showAvatar
        getAvatarData={(item) => ({ name: item.contact_name, color: '#4f46e5' })}
        actionVariant="menu"
        actions={actions}
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search lead, company..."
        isLoading={isLoading}
        toolbarActions={
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            className="border-slate-300 text-slate-900 font-bold hover:bg-slate-100 text-xs h-9"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

      {/* CREATE LEAD MODAL DIALOG */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-lg bg-white rounded-2xl border border-slate-300 shadow-2xl overflow-hidden text-black">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white">
                  <Plus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-black text-black">Create New Sales Lead</h3>
                  <p className="text-xs font-bold text-slate-700">Select company & organization from live API lists</p>
                </div>
              </div>
              <button
                type="button"
                onClick={handleCloseModal}
                className="p-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-200 transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              {errorMessage && (
                <Alert variant="destructive" className="bg-rose-50 border-rose-300 text-rose-950 font-bold">
                  <AlertCircle className="h-4 w-4 text-rose-600 mr-2" />
                  <AlertDescription className="text-rose-900 font-bold text-xs">
                    {errorMessage}
                  </AlertDescription>
                </Alert>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-xs font-black text-black">Contact Name *</Label>
                  <Input
                    type="text"
                    required
                    placeholder="e.g. John Doe"
                    value={contactName}
                    onChange={(e) => setContactName(e.target.value)}
                    className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-black text-black">Select Company *</Label>
                  <select
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    {isCompaniesLoading ? (
                      <option value="">Loading companies...</option>
                    ) : (
                      companies.map((c) => (
                        <option key={c.id} value={c.name}>
                          {c.name}
                        </option>
                      ))
                    )}
                    <option value="other">+ Enter Custom Company...</option>
                  </select>
                </div>
              </div>

              {company === 'other' && (
                <div className="space-y-1.5 animate-in fade-in-50">
                  <Label className="text-xs font-black text-black">Custom Company Name *</Label>
                  <Input
                    type="text"
                    required
                    placeholder="Enter new company name..."
                    value={customCompany}
                    onChange={(e) => setCustomCompany(e.target.value)}
                    className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                  />
                </div>
              )}

              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Opportunity / Lead Title</Label>
                <Input
                  type="text"
                  placeholder="e.g. Enterprise Cloud Deal"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-xs font-black text-black">Email Address *</Label>
                  <Input
                    type="email"
                    required
                    placeholder="john@acmecorp.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-black text-black">Phone Number</Label>
                  <Input
                    type="tel"
                    placeholder="+1 (555) 000-0000"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                <div className="space-y-1.5">
                  <Label className="text-xs font-black text-black">Lead Status</Label>
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="New">New</option>
                    <option value="Contacted">Contacted</option>
                    <option value="Qualified">Qualified</option>
                    <option value="Unqualified">Unqualified</option>
                    <option value="Converted">Converted</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs font-black text-black">Lead Source</Label>
                  <select
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="Website">Website</option>
                    <option value="LinkedIn">LinkedIn</option>
                    <option value="Referral">Referral</option>
                    <option value="Cold Call">Cold Call</option>
                    <option value="Event">Event</option>
                    <option value="Partner">Partner</option>
                  </select>
                </div>
              </div>

              {/* Dynamic API-connected Organization Dropdown List */}
              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Select Organization *</Label>
                <select
                  value={organizationId}
                  onChange={(e) => setOrganizationId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {isOrgsLoading ? (
                    <option value="">Loading organizations...</option>
                  ) : (
                    organizations.map((org) => (
                      <option key={org.id} value={org.id}>
                        {org.name} ({org.id})
                      </option>
                    ))
                  )}
                </select>
              </div>

              {/* Modal Actions */}
              <div className="pt-4 border-t border-slate-200 flex items-center justify-end gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCloseModal}
                  disabled={createLeadMutation.isPending}
                  className="border-slate-300 text-black font-bold hover:bg-slate-100 text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createLeadMutation.isPending}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold shadow-sm text-xs px-5"
                >
                  {createLeadMutation.isPending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                      Creating Lead...
                    </>
                  ) : (
                    'Create Lead'
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
