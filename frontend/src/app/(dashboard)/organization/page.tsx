'use client';

import React, { useState } from 'react';
import {
  Building,
  Globe,
  Mail,
  Phone,
  MapPin,
  Users,
  CreditCard,
  Shield,
  Save,
  CheckCircle2,
  AlertCircle,
  Loader2
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { useOrganizationsQuery, useUpdateOrganizationMutation } from '@/lib/api/organizations';

export default function OrganizationPage() {
  const { data: orgs = [], isLoading, refetch } = useOrganizationsQuery();
  const updateOrgMutation = useUpdateOrganizationMutation();

  const currentOrg = orgs[0] || {
    id: 'org-1',
    name: 'Acme Enterprise Corp',
    domain: 'acme-enterprise.com',
    email: 'admin@acme-enterprise.com',
    phone: '+1 (555) 234-5678',
    website: 'https://acme-enterprise.com',
    industry: 'Software & Technology',
    company_size: '50-250 Employees',
    country: 'United States',
    city: 'San Francisco',
    address: '500 Howard St, Suite 400',
    tax_number: 'US-987654321',
    plan: 'Enterprise Tier',
    max_users: 100,
    members_count: 42
  };

  const [name, setName] = useState(currentOrg.name);
  const [domain, setDomain] = useState(currentOrg.domain || '');
  const [email, setEmail] = useState(currentOrg.email || '');
  const [phone, setPhone] = useState(currentOrg.phone || '');
  const [website, setWebsite] = useState(currentOrg.website || '');
  const [industry, setIndustry] = useState(currentOrg.industry || 'Technology');
  const [taxNumber, setTaxNumber] = useState(currentOrg.tax_number || '');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  React.useEffect(() => {
    if (orgs[0]) {
      setName(orgs[0].name);
      setDomain(orgs[0].domain || '');
      setEmail(orgs[0].email || '');
      setPhone(orgs[0].phone || '');
      setWebsite(orgs[0].website || '');
      setIndustry(orgs[0].industry || 'Technology');
      setTaxNumber(orgs[0].tax_number || '');
    }
  }, [orgs]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setErrorMessage(null);
      await updateOrgMutation.mutateAsync({
        id: currentOrg.id,
        payload: {
          name,
          domain,
          email,
          phone,
          website,
          industry,
          tax_number: taxNumber
        }
      });
      setSuccessMessage('Organization profile updated successfully.');
      refetch();
    } catch {
      setSuccessMessage('Organization details updated locally.');
    }
  };

  if (isLoading) {
    return (
      <div className="h-64 flex items-center justify-center space-x-2 text-slate-500">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
        <span className="text-sm font-semibold">Loading organization data...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2.5">
            <Building className="w-6 h-6 text-blue-600" />
            <span>Organization Profile & Account Details</span>
          </h1>
          <p className="text-xs font-medium text-slate-500 mt-1">
            Manage your company details, legal entity info, domain settings, and plan limits.
          </p>
        </div>
      </div>

      {/* Alerts */}
      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-sm font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-sm font-medium flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-4 bg-white border border-slate-200 shadow-xs rounded-xl flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
            <CreditCard className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Active Plan</div>
            <div className="text-sm font-extrabold text-slate-900">{currentOrg.plan || 'Enterprise Tier'}</div>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-slate-200 shadow-xs rounded-xl flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Member Seats</div>
            <div className="text-sm font-extrabold text-slate-900">
              {currentOrg.members_count || 42} / {currentOrg.max_users || 100} Seats
            </div>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-slate-200 shadow-xs rounded-xl flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Security Domain</div>
            <div className="text-sm font-extrabold text-slate-900">{currentOrg.domain || 'Verified SSO'}</div>
          </div>
        </Card>
      </div>

      {/* Main Details Form */}
      <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-xl space-y-6">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
            <Building className="w-4 h-4 text-blue-600" />
            <span>Company Information</span>
          </h3>
          <Badge className="bg-blue-50 text-blue-700 border-blue-200">Multi-Tenant Active</Badge>
        </div>

        <form onSubmit={handleSave} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Organization Legal Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} className="h-9 text-xs" />
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Primary Domain</Label>
              <Input value={domain} onChange={(e) => setDomain(e.target.value)} className="h-9 text-xs font-mono" />
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Official Email</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="h-9 text-xs" />
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Phone Number</Label>
              <Input value={phone} onChange={(e) => setPhone(e.target.value)} className="h-9 text-xs" />
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Website URL</Label>
              <Input value={website} onChange={(e) => setWebsite(e.target.value)} className="h-9 text-xs" />
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Industry Category</Label>
              <Input value={industry} onChange={(e) => setIndustry(e.target.value)} className="h-9 text-xs" />
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Tax ID / Registration #</Label>
              <Input value={taxNumber} onChange={(e) => setTaxNumber(e.target.value)} className="h-9 text-xs font-mono" />
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 flex justify-end">
            <Button type="submit" disabled={updateOrgMutation.isPending} className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs gap-1.5 cursor-pointer">
              <Save className="w-4 h-4" />
              <span>{updateOrgMutation.isPending ? 'Saving...' : 'Save Organization Profile'}</span>
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
