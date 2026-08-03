'use client';

import React, { useState } from 'react';
import { 
  Plus, 
  Search, 
  Users, 
  Building2, 
  Mail, 
  Phone, 
  X, 
  Loader2, 
  CheckCircle2, 
  AlertCircle,
  Sparkles,
  RefreshCw,
  Globe
} from 'lucide-react';
import { Button, Card, CardHeader, CardTitle, CardDescription, CardContent, Input, Label, Badge, Alert, AlertDescription } from '@/components/ui';
import { useLeadsQuery, useCreateLeadMutation } from '@/lib/api/leads';
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
    if (organizations.length > 0) {
      setOrganizationId(organizations[0].id);
    }
    if (companies.length > 0) {
      setCompany(companies[0].name);
    }
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

      // Auto-hide success message after 4 seconds
      setTimeout(() => {
        setSuccessMessage(null);
      }, 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to create lead. Please check API server.');
    }
  };

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

      {/* Search and Filters Bar */}
      <Card className="border border-slate-300 bg-white p-4 shadow-xs">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="relative w-full sm:w-80">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <Input
              type="text"
              placeholder="Search leads by name or company..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 bg-slate-50 border-slate-300 text-black font-bold placeholder:text-slate-500 text-xs"
            />
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">All Statuses</option>
              <option value="New">New</option>
              <option value="Contacted">Contacted</option>
              <option value="Qualified">Qualified</option>
              <option value="Unqualified">Unqualified</option>
              <option value="Converted">Converted</option>
            </select>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              className="border-slate-300 text-black font-bold hover:bg-slate-100 text-xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </Card>

      {/* Leads Data Table */}
      <Card className="border border-slate-300 bg-white shadow-xs overflow-hidden">
        <CardHeader className="border-b border-slate-200 bg-slate-50/50 py-4 px-6">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-black text-black">
                Active Leads ({leads.length})
              </CardTitle>
              <CardDescription className="text-slate-800 font-bold">
                Real-time lead response from backend API
              </CardDescription>
            </div>
            <Badge variant="outline" className="bg-indigo-50 text-indigo-700 border-indigo-200 font-black">
              Railway API Connected
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="py-16 flex flex-col items-center justify-center space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
              <p className="text-xs font-bold text-slate-700">Loading leads from API...</p>
            </div>
          ) : isError ? (
            <div className="py-12 px-6 text-center space-y-3">
              <AlertCircle className="w-8 h-8 text-rose-500 mx-auto" />
              <p className="text-sm font-bold text-black">Could not fetch leads from server.</p>
              <Button size="sm" onClick={() => refetch()} className="bg-indigo-600 text-white font-bold">
                Retry Connection
              </Button>
            </div>
          ) : leads.length === 0 ? (
            <div className="py-16 text-center space-y-4">
              <Users className="w-12 h-12 text-slate-400 mx-auto" />
              <div>
                <p className="text-base font-black text-black">No leads found</p>
                <p className="text-xs font-bold text-slate-700 mt-1">Click "+ Add New Lead" above to create your first sales lead.</p>
              </div>
              <Button type="button" onClick={handleOpenModal} size="sm" className="bg-indigo-600 text-white font-bold">
                <Plus className="w-4 h-4 mr-1.5" />
                Add New Lead
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-100 text-xs font-black text-black uppercase tracking-wider">
                    <th className="py-3.5 px-6">Contact & Title</th>
                    <th className="py-3.5 px-6">Company</th>
                    <th className="py-3.5 px-6">Email & Phone</th>
                    <th className="py-3.5 px-6">Status</th>
                    <th className="py-3.5 px-6">Source</th>
                    <th className="py-3.5 px-6 text-right">AI Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {leads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-slate-50 transition duration-150">
                      <td className="py-4 px-6 font-black text-black">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-xl bg-indigo-100 border border-indigo-200 flex items-center justify-center font-black text-indigo-700 text-xs shrink-0">
                            {lead.contact_name ? lead.contact_name.charAt(0).toUpperCase() : 'L'}
                          </div>
                          <div>
                            <span className="block text-sm font-black text-black">{lead.contact_name}</span>
                            <span className="text-xs font-bold text-slate-700">{lead.title}</span>
                          </div>
                        </div>
                      </td>
                      <td className="py-4 px-6 font-bold text-black">
                        <div className="flex items-center gap-1.5">
                          <Building2 className="w-3.5 h-3.5 text-slate-500" />
                          <span>{lead.company}</span>
                        </div>
                      </td>
                      <td className="py-4 px-6 text-xs font-bold text-black space-y-1">
                        <div className="flex items-center gap-1.5">
                          <Mail className="w-3.5 h-3.5 text-indigo-600" />
                          <span>{lead.email}</span>
                        </div>
                        {lead.phone && (
                          <div className="flex items-center gap-1.5 text-slate-700">
                            <Phone className="w-3.5 h-3.5 text-slate-500" />
                            <span>{lead.phone}</span>
                          </div>
                        )}
                      </td>
                      <td className="py-4 px-6">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-black border ${
                          lead.status === 'New' ? 'bg-blue-50 text-blue-800 border-blue-200' :
                          lead.status === 'Qualified' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' :
                          lead.status === 'Contacted' ? 'bg-amber-50 text-amber-800 border-amber-200' :
                          'bg-slate-100 text-slate-800 border-slate-200'
                        }`}>
                          {lead.status}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-xs font-bold text-slate-800">
                        {lead.source}
                      </td>
                      <td className="py-4 px-6 text-right font-black">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-purple-50 text-purple-800 border border-purple-200 text-xs">
                          <Sparkles className="w-3 h-3 text-purple-600" />
                          {lead.score ?? 75}/100
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* CREATE LEAD MODAL DIALOG WITH API-CONNECTED SELECT LISTS */}
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
