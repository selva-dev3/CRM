'use client';

import React, { useState, useEffect } from 'react';
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
  Loader2,
  Upload,
  Plus,
  Trash2,
  Zap,
  Check,
  HardDrive,
  UserCheck,
  ShieldAlert,
  Crown,
  Lock,
  ArrowRightLeft,
  FileText
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  useCurrentOrganizationQuery,
  useOrganizationsQuery,
  useUpdateOrganizationMutation,
  useCreateOrganizationMutation,
  useOrganizationMembersQuery,
  useRemoveOrganizationMemberMutation,
  useOrganizationSubscriptionQuery,
  useUpgradeSubscriptionMutation,
  useCancelSubscriptionMutation,
  useOrganizationUsageQuery,
  useUpdateBrandingMutation,
  useVerifyDomainMutation,
  useOrganizationDomainsQuery,
  useOrganizationAuditLogsQuery,
  useTransferOwnershipMutation
} from '@/lib/api/organizations';

export default function OrganizationPage() {
  const [activeTab, setActiveTab] = useState<
    'profile' | 'branding' | 'members' | 'subscription' | 'usage' | 'domains' | 'ownership'
  >('profile');

  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Queries
  const { data: currentOrg, isLoading: isCurrentOrgLoading, refetch: refetchCurrentOrg } = useCurrentOrganizationQuery();
  const { data: allOrgs = [] } = useOrganizationsQuery();
  const { data: members = [], refetch: refetchMembers } = useOrganizationMembersQuery();
  const { data: subscription, refetch: refetchSubscription } = useOrganizationSubscriptionQuery();
  const { data: usage } = useOrganizationUsageQuery();
  const { data: domains = [], refetch: refetchDomains } = useOrganizationDomainsQuery();
  const { data: auditLogs = [] } = useOrganizationAuditLogsQuery();

  // Mutations
  const updateOrgMutation = useUpdateOrganizationMutation();
  const createOrgMutation = useCreateOrganizationMutation();
  const removeMemberMutation = useRemoveOrganizationMemberMutation();
  const upgradeSubMutation = useUpgradeSubscriptionMutation();
  const cancelSubMutation = useCancelSubscriptionMutation();
  const updateBrandingMutation = useUpdateBrandingMutation();
  const verifyDomainMutation = useVerifyDomainMutation();
  const transferOwnershipMutation = useTransferOwnershipMutation();

  // Profile Form States
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [website, setWebsite] = useState('');
  const [industry, setIndustry] = useState('');
  const [country, setCountry] = useState('');
  const [city, setCity] = useState('');
  const [address, setAddress] = useState('');
  const [taxNumber, setTaxNumber] = useState('');
  const [currency, setCurrency] = useState('INR');
  const [timezone, setTimezone] = useState('Asia/Kolkata');

  // Create Org Modal
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newOrgName, setNewOrgName] = useState('');
  const [newOrgDomain, setNewOrgDomain] = useState('');

  // Branding States
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [primaryColor, setPrimaryColor] = useState('#2563EB');

  // Domain Verification States
  const [domainToVerify, setDomainToVerify] = useState('');

  // Transfer Ownership States
  const [newOwnerUserId, setNewOwnerUserId] = useState('');

  // Populate profile form when data is loaded
  useEffect(() => {
    if (currentOrg) {
      setName(currentOrg.name || '');
      setSlug(currentOrg.slug || '');
      setEmail(currentOrg.email || '');
      setPhone(currentOrg.phone || '');
      setWebsite(currentOrg.website || '');
      setIndustry(currentOrg.industry || '');
      setCountry(currentOrg.country || '');
      setCity(currentOrg.city || '');
      setAddress(currentOrg.address || '');
      setTaxNumber(currentOrg.tax_number || '');
      setCurrency(currentOrg.currency || 'INR');
      setTimezone(currentOrg.timezone || 'Asia/Kolkata');
    }
  }, [currentOrg]);

  // Handlers
  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg?.id) return;
    try {
      setErrorMessage(null);
      await updateOrgMutation.mutateAsync({
        id: currentOrg.id,
        payload: {
          name,
          slug,
          email,
          phone,
          website,
          industry,
          country,
          city,
          address,
          tax_number: taxNumber,
          currency,
          timezone
        }
      });
      setSuccessMessage('Organization profile settings updated successfully.');
      refetchCurrentOrg();
    } catch {
      setErrorMessage('Failed to update organization profile.');
    }
  };

  const handleCreateOrganization = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newOrgName) return;
    try {
      setErrorMessage(null);
      await createOrgMutation.mutateAsync({
        name: newOrgName,
        domain: newOrgDomain || `${newOrgName.toLowerCase().replace(/\s+/g, '-')}.crm.com`,
        plan: 'Enterprise',
        max_users: 100
      });
      setSuccessMessage(`Organization "${newOrgName}" created successfully.`);
      setIsCreateModalOpen(false);
      setNewOrgName('');
      setNewOrgDomain('');
      refetchCurrentOrg();
    } catch {
      setErrorMessage('Failed to create new organization.');
    }
  };

  const handleBrandingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setErrorMessage(null);
      const formData = new FormData();
      if (logoFile) {
        formData.append('logo_file', logoFile);
      }
      formData.append('primary_color', primaryColor);
      const res = await updateBrandingMutation.mutateAsync(formData);
      setSuccessMessage(res.message || 'Branding updated & logo uploaded to MinIO S3.');
      refetchCurrentOrg();
    } catch {
      setErrorMessage('Failed to update branding S3 asset.');
    }
  };

  const handleRemoveMember = async (userId: string) => {
    try {
      setErrorMessage(null);
      const res = await removeMemberMutation.mutateAsync(userId);
      setSuccessMessage(res.message || 'Member removed from organization.');
      refetchMembers();
    } catch {
      setErrorMessage('Failed to remove member.');
    }
  };

  const handleUpgradePlan = async (planName: string) => {
    try {
      setErrorMessage(null);
      const res = await upgradeSubMutation.mutateAsync(planName);
      setSuccessMessage(res.message || `Upgraded subscription to ${planName}.`);
      refetchSubscription();
      refetchCurrentOrg();
    } catch {
      setErrorMessage('Failed to upgrade subscription plan.');
    }
  };

  const handleCancelSub = async () => {
    try {
      setErrorMessage(null);
      const res = await cancelSubMutation.mutateAsync();
      setSuccessMessage(res.message || 'Subscription cancelled.');
      refetchSubscription();
    } catch {
      setErrorMessage('Failed to cancel subscription.');
    }
  };

  const handleVerifyDomain = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!domainToVerify) return;
    try {
      setErrorMessage(null);
      const res = await verifyDomainMutation.mutateAsync(domainToVerify);
      setSuccessMessage(res.message || `Domain ${domainToVerify} verified.`);
      setDomainToVerify('');
      refetchDomains();
    } catch {
      setErrorMessage('Domain DNS verification failed.');
    }
  };

  const handleTransferOwnership = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newOwnerUserId) return;
    try {
      setErrorMessage(null);
      const res = await transferOwnershipMutation.mutateAsync(newOwnerUserId);
      setSuccessMessage(res.message || `Ownership transferred to user ID ${newOwnerUserId}.`);
      setNewOwnerUserId('');
    } catch {
      setErrorMessage('Failed to transfer organization ownership.');
    }
  };

  if (isCurrentOrgLoading) {
    return (
      <div className="h-64 flex flex-col items-center justify-center space-y-3 text-slate-500">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        <span className="text-sm font-semibold">Fetching Organization Data from REST APIs...</span>
      </div>
    );
  }

  const activeOrg = currentOrg || {
    id: 'org-1',
    name: 'Default Enterprise Organization',
    domain: 'enterprise.crm.com',
    plan: 'Enterprise',
    max_users: 100,
    created_at: '2026-01-01'
  };

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2.5">
            <Building className="w-6 h-6 text-blue-600" />
            <span>Organization Management</span>
          </h1>
          <p className="text-xs font-medium text-slate-500 mt-1">
            Configure enterprise profile, member roles, S3 branding assets, DNS verification, and usage quotas.
          </p>
        </div>

        <Button
          onClick={() => setIsCreateModalOpen(true)}
          className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold gap-1.5 cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Create New Org</span>
        </Button>
      </div>

      {/* Alert Banners */}
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

      {/* Top Usage & Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card className="p-4 bg-white border border-slate-200 shadow-xs rounded-xl flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
            <Building className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="text-[10px] font-bold text-slate-400 uppercase">Current Org</div>
            <div className="text-xs font-extrabold text-slate-900 truncate">{activeOrg.name}</div>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-slate-200 shadow-xs rounded-xl flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
            <Crown className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[10px] font-bold text-slate-400 uppercase">Subscription</div>
            <div className="text-xs font-extrabold text-slate-900">{subscription?.plan || activeOrg.plan || 'Enterprise'} Plan</div>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-slate-200 shadow-xs rounded-xl flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[10px] font-bold text-slate-400 uppercase">User Quota</div>
            <div className="text-xs font-extrabold text-slate-900">
              {usage?.users_used ?? 1} / {usage?.users_limit ?? activeOrg.max_users ?? 100} Seats
            </div>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-slate-200 shadow-xs rounded-xl flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
            <HardDrive className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[10px] font-bold text-slate-400 uppercase">S3 Storage Limit</div>
            <div className="text-xs font-extrabold text-slate-900">
              {usage?.storage_gb_used ?? 0.5} GB / {usage?.storage_gb_limit ?? 500} GB
            </div>
          </div>
        </Card>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center border-b border-slate-200 gap-4 text-xs font-semibold text-slate-600 overflow-x-auto">
        <button
          onClick={() => setActiveTab('profile')}
          className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
            activeTab === 'profile' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Building className="w-4 h-4" />
          <span>Org Profile & Details</span>
        </button>

        <button
          onClick={() => setActiveTab('branding')}
          className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
            activeTab === 'branding' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Upload className="w-4 h-4" />
          <span>S3 Branding & Logo</span>
        </button>

        <button
          onClick={() => setActiveTab('members')}
          className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
            activeTab === 'members' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <UserCheck className="w-4 h-4" />
          <span>Members & Team</span>
        </button>

        <button
          onClick={() => setActiveTab('subscription')}
          className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
            activeTab === 'subscription' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <CreditCard className="w-4 h-4" />
          <span>Subscription & Billing</span>
        </button>

        <button
          onClick={() => setActiveTab('usage')}
          className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
            activeTab === 'usage' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Zap className="w-4 h-4" />
          <span>Usage Quotas</span>
        </button>

        <button
          onClick={() => setActiveTab('domains')}
          className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
            activeTab === 'domains' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Globe className="w-4 h-4" />
          <span>Custom Domains</span>
        </button>

        <button
          onClick={() => setActiveTab('ownership')}
          className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
            activeTab === 'ownership' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <ArrowRightLeft className="w-4 h-4" />
          <span>Ownership Transfer</span>
        </button>
      </div>

      {/* TAB 1: PROFILE & DETAILS */}
      {activeTab === 'profile' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-xl space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
              <Building className="w-4 h-4 text-blue-600" />
              <span>Organization Details</span>
            </h3>
            <div className="flex items-center gap-2">
              <Badge className="bg-blue-50 text-blue-700 border-blue-200 font-mono text-[11px]">
                ID: {activeOrg.id}
              </Badge>
            </div>
          </div>

          <form onSubmit={handleUpdateProfile} className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Organization Name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} className="h-9 text-xs" />
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Slug Identifier</Label>
                <Input value={slug} onChange={(e) => setSlug(e.target.value)} className="h-9 text-xs font-mono" />
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
                <Label className="font-semibold text-slate-700">Industry Sector</Label>
                <Input value={industry} onChange={(e) => setIndustry(e.target.value)} className="h-9 text-xs" />
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Country</Label>
                <Input value={country} onChange={(e) => setCountry(e.target.value)} className="h-9 text-xs" />
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">City</Label>
                <Input value={city} onChange={(e) => setCity(e.target.value)} className="h-9 text-xs" />
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Tax / GSTIN Number</Label>
                <Input value={taxNumber} onChange={(e) => setTaxNumber(e.target.value)} className="h-9 text-xs font-mono" />
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Primary Currency</Label>
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="w-full h-9 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-900"
                >
                  <option value="INR">INR (₹)</option>
                  <option value="USD">USD ($)</option>
                  <option value="EUR">EUR (€)</option>
                  <option value="GBP">GBP (£)</option>
                </select>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-100 flex justify-end">
              <Button
                type="submit"
                disabled={updateOrgMutation.isPending}
                className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs gap-1.5 cursor-pointer"
              >
                <Save className="w-4 h-4" />
                <span>{updateOrgMutation.isPending ? 'Saving...' : 'Save Organization Profile'}</span>
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* TAB 2: BRANDING & S3 UPLOAD */}
      {activeTab === 'branding' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-xl space-y-6">
          <div className="border-b border-slate-100 pb-3">
            <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
              <Upload className="w-4 h-4 text-blue-600" />
              <span>MinIO S3 Branding & Logo Upload</span>
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Upload custom company logo to MinIO S3 object storage for branded quotes, emails, and header displays.
            </p>
          </div>

          <form onSubmit={handleBrandingSubmit} className="space-y-4 text-xs max-w-md">
            <div className="space-y-2">
              <Label className="font-semibold text-slate-700">Select Company Logo File</Label>
              <Input
                type="file"
                accept="image/*"
                onChange={(e) => setLogoFile(e.target.files?.[0] || null)}
                className="h-10 text-xs cursor-pointer"
              />
            </div>

            <div className="space-y-2">
              <Label className="font-semibold text-slate-700">Brand Accent Color</Label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-10 h-10 rounded border border-slate-300 cursor-pointer"
                />
                <Input value={primaryColor} onChange={(e) => setPrimaryColor(e.target.value)} className="h-9 text-xs font-mono w-32" />
              </div>
            </div>

            <div className="pt-2">
              <Button
                type="submit"
                disabled={updateBrandingMutation.isPending}
                className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs gap-1.5 cursor-pointer"
              >
                <Upload className="w-4 h-4" />
                <span>{updateBrandingMutation.isPending ? 'Uploading to S3...' : 'Upload Branding to S3'}</span>
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* TAB 3: MEMBERS */}
      {activeTab === 'members' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-blue-600" />
              <span>Organization Members</span>
            </h3>
            <Badge variant="outline" className="bg-slate-50 text-slate-700 border-slate-300">
              {members.length} Total Members
            </Badge>
          </div>

          <div className="space-y-3">
            {members.length > 0 ? (
              members.map((m) => (
                <div key={m.id} className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between text-xs">
                  <div>
                    <div className="font-bold text-slate-900">{m.name}</div>
                    <div className="text-[11px] text-slate-500 font-mono">{m.email} • {m.role}</div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleRemoveMember(m.id)}
                    disabled={removeMemberMutation.isPending}
                    className="h-8 text-xs border-rose-200 text-rose-600 hover:bg-rose-50"
                  >
                    <Trash2 className="w-3.5 h-3.5 mr-1" />
                    Remove
                  </Button>
                </div>
              ))
            ) : (
              <div className="p-6 text-center text-xs text-slate-500 bg-slate-50 rounded-lg">
                No extra members listed. Standard default tenant admin is assigned.
              </div>
            )}
          </div>
        </Card>
      )}

      {/* TAB 4: SUBSCRIPTION */}
      {activeTab === 'subscription' && (
        <div className="space-y-6">
          <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-blue-600" />
                <span>Subscription Details</span>
              </h3>
              <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200">Active Billing</Badge>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <div className="text-[10px] text-slate-400 font-bold uppercase">Plan Tier</div>
                <div className="text-sm font-extrabold text-slate-900 mt-0.5">{subscription?.plan || 'Enterprise'}</div>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <div className="text-[10px] text-slate-400 font-bold uppercase">Billing Cycle</div>
                <div className="text-sm font-extrabold text-slate-900 mt-0.5">{subscription?.billing_cycle || 'Monthly'}</div>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <div className="text-[10px] text-slate-400 font-bold uppercase">Monthly Price</div>
                <div className="text-sm font-extrabold text-slate-900 mt-0.5">${subscription?.amount || 299}/mo</div>
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <Button
                onClick={() => handleUpgradePlan('Enterprise Plus')}
                disabled={upgradeSubMutation.isPending}
                className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold cursor-pointer"
              >
                Upgrade to Enterprise Plus
              </Button>
              <Button
                variant="outline"
                onClick={handleCancelSub}
                disabled={cancelSubMutation.isPending}
                className="border-rose-200 text-rose-600 hover:bg-rose-50 text-xs font-semibold cursor-pointer"
              >
                Cancel Subscription
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* TAB 5: USAGE METRICS */}
      {activeTab === 'usage' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-xl space-y-6">
          <div className="border-b border-slate-100 pb-3">
            <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
              <Zap className="w-4 h-4 text-blue-600" />
              <span>Usage Metrics & Quotas</span>
            </h3>
          </div>

          <div className="space-y-6 text-xs max-w-xl">
            <div className="space-y-2">
              <div className="flex justify-between font-semibold text-slate-700">
                <span>Active User Seats</span>
                <span>{usage?.users_used ?? 1} / {usage?.users_limit ?? 100}</span>
              </div>
              <div className="w-full h-2.5 rounded-full bg-slate-100 overflow-hidden">
                <div className="h-full bg-blue-600 rounded-full" style={{ width: `${((usage?.users_used ?? 1) / (usage?.users_limit ?? 100)) * 100}%` }} />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between font-semibold text-slate-700">
                <span>MinIO S3 Storage</span>
                <span>{usage?.storage_gb_used ?? 0.5} GB / {usage?.storage_gb_limit ?? 500} GB</span>
              </div>
              <div className="w-full h-2.5 rounded-full bg-slate-100 overflow-hidden">
                <div className="h-full bg-purple-600 rounded-full" style={{ width: `${((usage?.storage_gb_used ?? 0.5) / (usage?.storage_gb_limit ?? 500)) * 100}%` }} />
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* TAB 6: CUSTOM DOMAINS */}
      {activeTab === 'domains' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-xl space-y-4">
          <div className="border-b border-slate-100 pb-3">
            <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
              <Globe className="w-4 h-4 text-blue-600" />
              <span>Custom Domain TXT DNS Verification</span>
            </h3>
          </div>

          <form onSubmit={handleVerifyDomain} className="space-y-3 text-xs max-w-md">
            <Label className="font-semibold text-slate-700">Domain Name to Verify</Label>
            <div className="flex gap-2">
              <Input
                placeholder="crm.yourcompany.com"
                value={domainToVerify}
                onChange={(e) => setDomainToVerify(e.target.value)}
                className="h-9 text-xs"
              />
              <Button
                type="submit"
                disabled={verifyDomainMutation.isPending}
                className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold cursor-pointer shrink-0"
              >
                Verify Domain TXT
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* TAB 7: OWNERSHIP TRANSFER */}
      {activeTab === 'ownership' && (
        <Card className="p-6 bg-white border border-rose-200 bg-rose-50/20 shadow-xs rounded-xl space-y-4">
          <div className="border-b border-rose-100 pb-3">
            <h3 className="font-bold text-rose-900 text-base flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-600" />
              <span>Transfer Primary Organization Ownership</span>
            </h3>
            <p className="text-xs text-slate-600 mt-1">
              Transfer legal primary owner rights and superadmin privileges to another user.
            </p>
          </div>

          <form onSubmit={handleTransferOwnership} className="space-y-3 text-xs max-w-md">
            <Label className="font-semibold text-slate-700">Target User ID</Label>
            <div className="flex gap-2">
              <Input
                placeholder="usr_12345"
                value={newOwnerUserId}
                onChange={(e) => setNewOwnerUserId(e.target.value)}
                className="h-9 text-xs font-mono"
              />
              <Button
                type="submit"
                disabled={transferOwnershipMutation.isPending}
                className="bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold cursor-pointer shrink-0"
              >
                Transfer Ownership
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* CREATE NEW ORGANIZATION MODAL */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-md bg-white rounded-2xl border border-slate-300 shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <Building className="w-5 h-5 text-blue-600" />
                <span>Create New Organization</span>
              </h3>
              <button type="button" onClick={() => setIsCreateModalOpen(false)} className="text-slate-400 hover:text-slate-700">
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateOrganization} className="space-y-4 text-xs">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Organization Name</Label>
                <Input
                  type="text"
                  placeholder="e.g. Global Trade Ltd"
                  value={newOrgName}
                  onChange={(e) => setNewOrgName(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Custom Domain / Subdomain</Label>
                <Input
                  type="text"
                  placeholder="e.g. globaltrade.crm.com"
                  value={newOrgDomain}
                  onChange={(e) => setNewOrgDomain(e.target.value)}
                  className="h-9 text-xs font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setIsCreateModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={createOrgMutation.isPending} className="bg-blue-600 text-white font-semibold">
                  {createOrgMutation.isPending ? 'Creating...' : 'Create Organization'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
