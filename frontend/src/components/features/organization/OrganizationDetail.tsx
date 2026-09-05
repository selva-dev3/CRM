'use client';
/* eslint-disable @next/next/no-img-element -- remote organization logo URL */

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  Building,
  ArrowLeft,
  Globe,
  Users,
  CreditCard,
  Save,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Upload,
  Trash2,
  Zap,
  HardDrive,
  UserCheck,
  ShieldAlert,
  Crown,
  ArrowRightLeft,
  FileText,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  useCurrentOrganizationQuery,
  useOrganizationByIdQuery,
  useUpdateOrganizationMutation,
  useOrganizationMembersQuery,
  useRemoveOrganizationMemberMutation,
  useOrganizationSubscriptionQuery,
  useCancelSubscriptionMutation,
  useOrganizationUsageQuery,
  useUpdateBrandingMutation,
  useVerifyDomainMutation,
  useOrganizationDomainsQuery,
  useOrganizationAuditLogsQuery,
  useTransferOwnershipMutation
} from '@/lib/api/organizations';

export default function OrganizationDetail({ isCurrentOrgView = false }: { isCurrentOrgView?: boolean }) {
  const router = useRouter();
  const params = useParams();
  const routeOrgId = typeof params?.id === 'string' ? params.id : '';

  const [activeTab, setActiveTab] = useState<
    'profile' | 'branding' | 'members' | 'subscription' | 'usage' | 'domains' | 'ownership'
  >('profile');

  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Queries
  const {
    data: currentOrg,
    isLoading: isCurrentLoading,
    isError: isCurrentError,
    refetch: refetchCurrent,
  } = useCurrentOrganizationQuery();
  const {
    data: orgById,
    isLoading: isOrgByIdLoading,
    isError: isOrgByIdError,
    refetch: refetchById,
  } = useOrganizationByIdQuery(routeOrgId, !isCurrentOrgView);

  const org = isCurrentOrgView ? currentOrg : orgById;
  const orgId = org?.id || routeOrgId;
  const isOrgLoading = isCurrentOrgView ? isCurrentLoading : isOrgByIdLoading;
  const isOrgError = isCurrentOrgView ? isCurrentError : isOrgByIdError;
  const refetchOrg = isCurrentOrgView ? refetchCurrent : refetchById;
  const { data: members = [], refetch: refetchMembers } = useOrganizationMembersQuery();
  const { data: subscription, refetch: refetchSubscription } = useOrganizationSubscriptionQuery();
  const { data: usage } = useOrganizationUsageQuery();
  const { refetch: refetchDomains } = useOrganizationDomainsQuery();
  const { data: auditLogs = [] } = useOrganizationAuditLogsQuery();

  // Mutations
  const updateOrgMutation = useUpdateOrganizationMutation();
  const removeMemberMutation = useRemoveOrganizationMemberMutation();
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
  const [domain, setDomain] = useState('');
  const [industry, setIndustry] = useState('');
  const [country, setCountry] = useState('');
  const [city, setCity] = useState('');
  const [address, setAddress] = useState('');
  const [taxNumber, setTaxNumber] = useState('');
  const [currency, setCurrency] = useState('INR');
  const [timezone, setTimezone] = useState('Asia/Kolkata');
  const [plan, setPlan] = useState('Enterprise');
  const [maxUsers, setMaxUsers] = useState(100);
  const [status, setStatus] = useState('active');

  // Branding States
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [primaryColor, setPrimaryColor] = useState('#2563EB');

  // Domain Verification States
  const [domainToVerify, setDomainToVerify] = useState('');

  // Transfer Ownership States
  const [newOwnerUserId, setNewOwnerUserId] = useState('');

  // Populate profile form when organization data is loaded
  useEffect(() => {
    if (org) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate editable form from API data
      setName(org.name || '');
      setSlug(org.slug || '');
      setEmail(org.email || '');
      setPhone(org.phone || '');
      setWebsite(org.website || '');
      setDomain(org.domain || '');
      setIndustry(org.industry || '');
      setCountry(org.country || '');
      setCity(org.city || '');
      setAddress(org.address || '');
      setTaxNumber(org.tax_number || '');
      setCurrency(org.currency || 'INR');
      setTimezone(org.timezone || 'Asia/Kolkata');
      setPlan(org.plan || 'Enterprise');
      setMaxUsers(org.max_users || 100);
      setStatus(org.status || 'active');
    }
  }, [org]);

  // Handlers
  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!orgId) return;
    try {
      setErrorMessage(null);
      await updateOrgMutation.mutateAsync({
        id: orgId,
        payload: {
          name,
          slug,
          email,
          phone,
          website,
          domain,
          industry,
          country,
          city,
          address,
          tax_number: taxNumber,
          currency,
          timezone,
          plan,
          max_users: Number(maxUsers),
          status
        }
      });
      setSuccessMessage('Organization profile settings updated successfully.');
      refetchOrg();
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch {
      setErrorMessage('Failed to update organization profile.');
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
      refetchOrg();
      setTimeout(() => setSuccessMessage(null), 4000);
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
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch {
      setErrorMessage('Failed to remove member.');
    }
  };

  const handleCancelSub = async () => {
    try {
      setErrorMessage(null);
      const res = await cancelSubMutation.mutateAsync();
      setSuccessMessage(res.message || 'Subscription cancelled.');
      refetchSubscription();
      setTimeout(() => setSuccessMessage(null), 4000);
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
      setTimeout(() => setSuccessMessage(null), 4000);
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
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch {
      setErrorMessage('Failed to transfer organization ownership.');
    }
  };

  if (isOrgLoading) {
    return (
      <div className="h-64 flex flex-col items-center justify-center space-y-3 text-slate-500">
        <Loader2 className="w-8 h-8 animate-spin text-[#2563EB]" />
        <span className="text-body font-semibold">Loading Organization Details...</span>
      </div>
    );
  }

  if (isOrgError || !org) {
    return (
      <div className="h-64 flex flex-col items-center justify-center space-y-3 text-red-600" role="alert">
        <AlertCircle className="w-8 h-8" />
        <span className="text-body font-semibold">Unable to load organization details.</span>
      </div>
    );
  }

  const activeOrg = org;

  return (
    <div className="space-y-6 text-[#374151]">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-[#E5E7EB] w-full">
        <div className="w-full sm:w-auto min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-2">
            <button
              type="button"
              onClick={() => router.push('/settings')}
              className="text-caption font-semibold text-slate-600 hover:text-slate-900 flex items-center gap-1.5 cursor-pointer bg-white px-2.5 py-1 rounded-md border border-slate-300 shadow-xs transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5 text-slate-500" />
              <span>Back to Settings</span>
            </button>
          </div>
          <div className="flex items-start sm:items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-btn bg-[#2563EB] text-white flex items-center justify-center font-bold shadow-saas-sm shrink-0 mt-0.5 sm:mt-0">
              {activeOrg.logo_url ? (
                <img src={activeOrg.logo_url} alt={activeOrg.name} className="w-full h-full object-cover rounded-btn" />
              ) : (
                <Building className="w-5 h-5" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <h1 className="text-page-title flex flex-wrap items-center gap-2 break-words">
                <span className="break-words">{activeOrg.name}</span>
                <Badge className="bg-purple-50 text-purple-700 border-purple-200 text-badge font-mono shrink-0">
                  {activeOrg.plan || 'Enterprise'} Plan
                </Badge>
              </h1>
              <p className="text-caption text-[#6B7280] mt-0.5 font-mono truncate break-all">
                Domain: {activeOrg.domain || `${activeOrg.slug || 'org'}.crm.com`}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto justify-end shrink-0">
          <Button
            onClick={handleUpdateProfile}
            disabled={updateOrgMutation.isPending}
            variant="primary"
            className="shadow-saas-sm px-4 text-button cursor-pointer w-full sm:w-auto"
          >
            <Save className="w-4 h-4 mr-2" />
            <span>{updateOrgMutation.isPending ? 'Saving...' : 'Save Profile'}</span>
          </Button>
        </div>
      </div>

      {/* Alert Banners */}
      {successMessage && (
        <div className="p-4 rounded-btn bg-[#16A34A]/10 border border-[#16A34A]/20 text-[#16A34A] text-body font-medium flex items-center gap-2 animate-in fade-in-50">
          <CheckCircle2 className="w-5 h-5 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="p-4 rounded-btn bg-[#DC2626]/10 border border-[#DC2626]/20 text-[#DC2626] text-body font-medium flex items-center gap-2 animate-in fade-in-50">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Top Overview Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn flex items-center gap-3">
          <div className="w-10 h-10 rounded-btn bg-[#2563EB]/10 text-[#2563EB] flex items-center justify-center font-bold">
            <Building className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="text-caption font-bold text-[#9CA3AF] uppercase">Organization</div>
            <div className="text-body font-bold text-[#111827] truncate">{activeOrg.name}</div>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn flex items-center gap-3">
          <div className="w-10 h-10 rounded-btn bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
            <Crown className="w-5 h-5" />
          </div>
          <div>
            <div className="text-caption font-bold text-[#9CA3AF] uppercase">Subscription</div>
            <div className="text-body font-bold text-[#111827]">{activeOrg.plan || 'Enterprise'} Plan</div>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn flex items-center gap-3">
          <div className="w-10 h-10 rounded-btn bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <div className="text-caption font-bold text-[#9CA3AF] uppercase">User Quota</div>
            <div className="text-body font-bold text-[#111827]">
              {usage?.users_used ?? 1} / {activeOrg.max_users || 100} Seats
            </div>
          </div>
        </Card>

        <Card className="p-4 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn flex items-center gap-3">
          <div className="w-10 h-10 rounded-btn bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
            <HardDrive className="w-5 h-5" />
          </div>
          <div>
            <div className="text-caption font-bold text-[#9CA3AF] uppercase">S3 Storage Quota</div>
            <div className="text-body font-bold text-[#111827]">
              {usage?.storage_gb_used ?? 0.5} GB / {usage?.storage_gb_limit ?? 500} GB
            </div>
          </div>
        </Card>
      </div>

      {/* Detail Tabs Bar */}
      <div className="flex items-center border-b border-[#E5E7EB] gap-1.5 sm:gap-2 text-button font-medium text-[#6B7280] overflow-x-auto pb-2 scrollbar-none w-full">
        <button
          type="button"
          onClick={() => setActiveTab('profile')}
          className={`px-3 py-2 cursor-pointer transition rounded-btn flex items-center gap-2 shrink-0 whitespace-nowrap text-caption sm:text-button ${
            activeTab === 'profile'
              ? 'bg-[#2563EB]/10 text-[#2563EB] font-semibold border border-[#2563EB]/20 shadow-saas-sm'
              : 'hover:text-[#111827] hover:bg-[#F3F4F6]'
          }`}
        >
          <Building className="w-4 h-4 shrink-0" />
          <span>Org Profile & Details</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('branding')}
          className={`px-3 py-2 cursor-pointer transition rounded-btn flex items-center gap-2 shrink-0 whitespace-nowrap text-caption sm:text-button ${
            activeTab === 'branding'
              ? 'bg-[#2563EB]/10 text-[#2563EB] font-semibold border border-[#2563EB]/20 shadow-saas-sm'
              : 'hover:text-[#111827] hover:bg-[#F3F4F6]'
          }`}
        >
          <Upload className="w-4 h-4 shrink-0" />
          <span>S3 Branding & Logo</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('members')}
          className={`px-3 py-2 cursor-pointer transition rounded-btn flex items-center gap-2 shrink-0 whitespace-nowrap text-caption sm:text-button ${
            activeTab === 'members'
              ? 'bg-[#2563EB]/10 text-[#2563EB] font-semibold border border-[#2563EB]/20 shadow-saas-sm'
              : 'hover:text-[#111827] hover:bg-[#F3F4F6]'
          }`}
        >
          <UserCheck className="w-4 h-4 shrink-0" />
          <span>Members & Team</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('subscription')}
          className={`px-3 py-2 cursor-pointer transition rounded-btn flex items-center gap-2 shrink-0 whitespace-nowrap text-caption sm:text-button ${
            activeTab === 'subscription'
              ? 'bg-[#2563EB]/10 text-[#2563EB] font-semibold border border-[#2563EB]/20 shadow-saas-sm'
              : 'hover:text-[#111827] hover:bg-[#F3F4F6]'
          }`}
        >
          <CreditCard className="w-4 h-4 shrink-0" />
          <span>Subscription & Billing</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('usage')}
          className={`px-3 py-2 cursor-pointer transition rounded-btn flex items-center gap-2 shrink-0 whitespace-nowrap text-caption sm:text-button ${
            activeTab === 'usage'
              ? 'bg-[#2563EB]/10 text-[#2563EB] font-semibold border border-[#2563EB]/20 shadow-saas-sm'
              : 'hover:text-[#111827] hover:bg-[#F3F4F6]'
          }`}
        >
          <Zap className="w-4 h-4 shrink-0" />
          <span>Usage Quotas</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('domains')}
          className={`px-3 py-2 cursor-pointer transition rounded-btn flex items-center gap-2 shrink-0 whitespace-nowrap text-caption sm:text-button ${
            activeTab === 'domains'
              ? 'bg-[#2563EB]/10 text-[#2563EB] font-semibold border border-[#2563EB]/20 shadow-saas-sm'
              : 'hover:text-[#111827] hover:bg-[#F3F4F6]'
          }`}
        >
          <Globe className="w-4 h-4 shrink-0" />
          <span>Custom Domains</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('ownership')}
          className={`px-3 py-2 cursor-pointer transition rounded-btn flex items-center gap-2 shrink-0 whitespace-nowrap text-caption sm:text-button ${
            activeTab === 'ownership'
              ? 'bg-[#2563EB]/10 text-[#2563EB] font-semibold border border-[#2563EB]/20 shadow-saas-sm'
              : 'hover:text-[#111827] hover:bg-[#F3F4F6]'
          }`}
        >
          <ArrowRightLeft className="w-4 h-4 shrink-0" />
          <span>Ownership & Audit Logs</span>
        </button>
      </div>

      {/* TAB 1: PROFILE & DETAILS */}
      {activeTab === 'profile' && (
        <Card className="p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn space-y-6">
          <div className="border-b border-[#E5E7EB] pb-3">
            <h3 className="font-semibold text-[#111827] text-subheading flex items-center gap-2">
              <Building className="w-5 h-5 text-[#2563EB]" />
              <span>Organization Details</span>
            </h3>
          </div>

          <form onSubmit={handleUpdateProfile} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="org-name">Organization Name</Label>
                <Input id="org-name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>

              <div>
                <Label htmlFor="org-slug">Slug Identifier</Label>
                <Input id="org-slug" value={slug} onChange={(e) => setSlug(e.target.value)} className="font-mono" />
              </div>

              <div>
                <Label htmlFor="org-email">Official Email</Label>
                <Input id="org-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>

              <div>
                <Label htmlFor="org-phone">Phone Number</Label>
                <Input id="org-phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
              </div>

              <div>
                <Label htmlFor="org-website">Website URL</Label>
                <Input id="org-website" value={website} onChange={(e) => setWebsite(e.target.value)} />
              </div>

              <div>
                <Label htmlFor="org-domain">Custom Domain</Label>
                <Input id="org-domain" value={domain} onChange={(e) => setDomain(e.target.value)} className="font-mono text-caption" />
              </div>

              <div>
                <Label htmlFor="org-industry">Industry Sector</Label>
                <Input id="org-industry" value={industry} onChange={(e) => setIndustry(e.target.value)} />
              </div>

              <div>
                <Label htmlFor="org-country">Country</Label>
                <Input id="org-country" value={country} onChange={(e) => setCountry(e.target.value)} />
              </div>

              <div>
                <Label htmlFor="org-city">City</Label>
                <Input id="org-city" value={city} onChange={(e) => setCity(e.target.value)} />
              </div>

              <div>
                <Label htmlFor="org-tax">Tax / GSTIN Number</Label>
                <Input id="org-tax" value={taxNumber} onChange={(e) => setTaxNumber(e.target.value)} className="font-mono" />
              </div>

              <div>
                <Label htmlFor="org-users">User Seats Limit</Label>
                <Input
                  id="org-users"
                  type="number"
                  min={1}
                  value={maxUsers}
                  onChange={(e) => setMaxUsers(Number(e.target.value))}
                />
              </div>
            </div>

            <div className="pt-4 border-t border-[#E5E7EB] flex justify-end">
              <Button
                type="submit"
                variant="primary"
                disabled={updateOrgMutation.isPending}
                className="cursor-pointer shadow-saas-sm"
              >
                <Save className="w-4 h-4 mr-2" />
                <span>{updateOrgMutation.isPending ? 'Saving...' : 'Save Organization Profile'}</span>
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* TAB 2: BRANDING & S3 UPLOAD */}
      {activeTab === 'branding' && (
        <Card className="p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn space-y-6">
          <div className="border-b border-[#E5E7EB] pb-3">
            <h3 className="font-semibold text-[#111827] text-subheading flex items-center gap-2">
              <Upload className="w-5 h-5 text-[#2563EB]" />
              <span>MinIO S3 Branding & Logo Upload</span>
            </h3>
            <p className="text-caption text-[#6B7280] mt-0.5">
              Upload custom company logo to MinIO S3 object storage for branded quotes, emails, and header displays.
            </p>
          </div>

          <form onSubmit={handleBrandingSubmit} className="space-y-4 max-w-md">
            <div>
              <Label htmlFor="logo-file">Select Company Logo File</Label>
              <Input
                id="logo-file"
                type="file"
                accept="image/*"
                onChange={(e) => setLogoFile(e.target.files?.[0] || null)}
                className="cursor-pointer"
              />
            </div>

            <div>
              <Label htmlFor="brand-color">Brand Accent Color</Label>
              <div className="flex items-center gap-3">
                <input
                  id="brand-color"
                  type="color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-10 h-10 rounded-btn border border-[#E5E7EB] cursor-pointer"
                />
                <Input value={primaryColor} onChange={(e) => setPrimaryColor(e.target.value)} className="font-mono w-36" />
              </div>
            </div>

            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                disabled={updateBrandingMutation.isPending}
                className="cursor-pointer shadow-saas-sm"
              >
                <Upload className="w-4 h-4 mr-2" />
                <span>{updateBrandingMutation.isPending ? 'Uploading to S3...' : 'Upload Branding to S3'}</span>
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* TAB 3: MEMBERS */}
      {activeTab === 'members' && (
        <Card className="p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn space-y-4">
          <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
            <h3 className="font-semibold text-[#111827] text-subheading flex items-center gap-2">
              <UserCheck className="w-5 h-5 text-[#2563EB]" />
              <span>Organization Members</span>
            </h3>
            <Badge variant="outline" className="bg-[#F9FAFB] text-[#374151] border-[#E5E7EB]">
              {members.length} Total Members
            </Badge>
          </div>

          <div className="space-y-3">
            {members.length > 0 ? (
              members.map((m) => (
                <div key={m.id} className="p-3 bg-[#F9FAFB] rounded-btn border border-[#E5E7EB] flex items-center justify-between text-body">
                  <div>
                    <div className="font-semibold text-[#111827]">{m.name}</div>
                    <div className="text-caption text-[#6B7280] font-mono">{m.email} • {m.role}</div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleRemoveMember(m.id)}
                    disabled={removeMemberMutation.isPending}
                    className="h-8 text-caption border-[#DC2626]/30 text-[#DC2626] hover:bg-[#DC2626]/10 cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5 mr-1" />
                    Remove
                  </Button>
                </div>
              ))
            ) : (
              <div className="p-6 text-center text-body text-[#6B7280] bg-[#F9FAFB] rounded-btn">
                Standard default tenant admin is assigned.
              </div>
            )}
          </div>
        </Card>
      )}

      {/* TAB 4: SUBSCRIPTION */}
      {activeTab === 'subscription' && (
        <Card className="p-4 sm:p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-4 border-b border-[#E5E7EB] pb-3">
            <h3 className="font-semibold text-[#111827] text-body sm:text-subheading flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-[#2563EB] shrink-0" />
              <span>Subscription & Billing Details</span>
            </h3>
            <Badge className="bg-[#16A34A]/10 text-[#16A34A] border-[#16A34A]/20 self-start sm:self-auto shrink-0">
              Active Billing
            </Badge>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
            <div className="p-3.5 sm:p-4 bg-[#F9FAFB] rounded-btn border border-[#E5E7EB]">
              <div className="text-caption text-[#9CA3AF] font-bold uppercase text-xs">Plan Tier</div>
              <div className="text-body sm:text-subheading font-bold text-[#111827] mt-0.5 break-words">
                {subscription?.plan || activeOrg.plan || 'Enterprise'}
              </div>
            </div>
            <div className="p-3.5 sm:p-4 bg-[#F9FAFB] rounded-btn border border-[#E5E7EB]">
              <div className="text-caption text-[#9CA3AF] font-bold uppercase text-xs">Billing Cycle</div>
              <div className="text-body sm:text-subheading font-bold text-[#111827] mt-0.5 break-words">
                {subscription?.billing_cycle || 'Monthly'}
              </div>
            </div>
            <div className="p-3.5 sm:p-4 bg-[#F9FAFB] rounded-btn border border-[#E5E7EB]">
              <div className="text-caption text-[#9CA3AF] font-bold uppercase text-xs">Price</div>
              <div className="text-body sm:text-subheading font-bold text-[#111827] mt-0.5 break-words">
                ₹{subscription?.amount || 29990}/mo
              </div>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 sm:gap-3 pt-2">
            <Button
              onClick={() => router.push(`/organization/subscription/plans?org_id=${encodeURIComponent(activeOrg.id)}`)}
              variant="primary"
              className="cursor-pointer shadow-saas-sm w-full sm:w-auto"
            >
              Upgrade Plan Tier
            </Button>
            <Button
              variant="outline"
              onClick={handleCancelSub}
              disabled={cancelSubMutation.isPending}
              className="border-[#DC2626]/30 text-[#DC2626] hover:bg-[#DC2626]/10 cursor-pointer font-semibold w-full sm:w-auto"
            >
              Cancel Subscription
            </Button>
          </div>
        </Card>
      )}

      {/* TAB 5: USAGE METRICS */}
      {activeTab === 'usage' && (
        <Card className="p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn space-y-6">
          <div className="border-b border-[#E5E7EB] pb-3">
            <h3 className="font-semibold text-[#111827] text-subheading flex items-center gap-2">
              <Zap className="w-5 h-5 text-[#2563EB]" />
              <span>Usage Metrics & Quotas</span>
            </h3>
          </div>

          <div className="space-y-6 max-w-xl">
            <div className="space-y-2">
              <div className="flex justify-between font-semibold text-[#374151]">
                <span>Active User Seats</span>
                <span>{usage?.users_used ?? 1} / {activeOrg.max_users || 100}</span>
              </div>
              <div className="w-full h-3 rounded-full bg-[#E5E7EB] overflow-hidden">
                <div className="h-full bg-[#2563EB] rounded-full" style={{ width: `${((usage?.users_used ?? 1) / (activeOrg.max_users || 100)) * 100}%` }} />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between font-semibold text-[#374151]">
                <span>MinIO S3 Storage</span>
                <span>{usage?.storage_gb_used ?? 0.5} GB / {usage?.storage_gb_limit ?? 500} GB</span>
              </div>
              <div className="w-full h-3 rounded-full bg-[#E5E7EB] overflow-hidden">
                <div className="h-full bg-purple-600 rounded-full" style={{ width: `${((usage?.storage_gb_used ?? 0.5) / (usage?.storage_gb_limit ?? 500)) * 100}%` }} />
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* TAB 6: CUSTOM DOMAINS */}
      {activeTab === 'domains' && (
        <Card className="p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn space-y-4">
          <div className="border-b border-[#E5E7EB] pb-3">
            <h3 className="font-semibold text-[#111827] text-subheading flex items-center gap-2">
              <Globe className="w-5 h-5 text-[#2563EB]" />
              <span>Custom Domain TXT DNS Verification</span>
            </h3>
          </div>

          <form onSubmit={handleVerifyDomain} className="space-y-3 max-w-md">
            <Label htmlFor="verify-domain">Domain Name to Verify</Label>
            <div className="flex gap-2">
              <Input
                id="verify-domain"
                placeholder="crm.yourcompany.com"
                value={domainToVerify}
                onChange={(e) => setDomainToVerify(e.target.value)}
              />
              <Button
                type="submit"
                variant="primary"
                disabled={verifyDomainMutation.isPending}
                className="cursor-pointer shrink-0 shadow-saas-sm"
              >
                Verify TXT
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* TAB 7: OWNERSHIP & AUDIT LOGS */}
      {activeTab === 'ownership' && (
        <div className="space-y-6">
          <Card className="p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn space-y-4">
            <div className="border-b border-[#E5E7EB] pb-3">
              <h3 className="font-semibold text-[#111827] text-subheading flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-[#DC2626]" />
                <span>Transfer Organization Ownership</span>
              </h3>
              <p className="text-caption text-[#6B7280] mt-1">
                Transfer legal primary owner rights and superadmin privileges to another user.
              </p>
            </div>

            <form onSubmit={handleTransferOwnership} className="space-y-3 max-w-md">
              <Label htmlFor="transfer-user">Target User ID</Label>
              <div className="flex gap-2">
                <Input
                  id="transfer-user"
                  placeholder="usr_12345"
                  value={newOwnerUserId}
                  onChange={(e) => setNewOwnerUserId(e.target.value)}
                  className="font-mono"
                />
                <Button
                  type="submit"
                  disabled={transferOwnershipMutation.isPending}
                  className="bg-[#DC2626] hover:bg-[#B91C1C] text-white font-semibold cursor-pointer shrink-0 shadow-saas-sm"
                >
                  Transfer Ownership
                </Button>
              </div>
            </form>
          </Card>

          {/* Audit Logs Table */}
          <Card className="p-4 sm:p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-btn space-y-4">
            <div className="border-b border-[#E5E7EB] pb-3">
              <h3 className="font-semibold text-[#111827] text-body sm:text-subheading flex items-center gap-2">
                <FileText className="w-5 h-5 text-[#2563EB] shrink-0" />
                <span>Audit Logs History</span>
              </h3>
            </div>

            <div className="space-y-2">
              {auditLogs.length > 0 ? (
                auditLogs.map((log) => (
                  <div
                    key={log.id}
                    className="p-3 sm:p-3.5 bg-[#F9FAFB] rounded-btn border border-[#E5E7EB] flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-4 text-body transition-colors hover:bg-[#F3F4F6]/60"
                  >
                    <div className="min-w-0 flex-1 space-y-0.5">
                      <div className="font-semibold text-[#111827] break-words text-caption sm:text-body">
                        {log.action}
                      </div>
                      <div className="text-caption text-[#6B7280] break-all sm:break-normal">
                        Actor: {log.actor} • IP: {log.ip || '127.0.0.1'}
                      </div>
                    </div>
                    <div className="text-caption text-[#9CA3AF] font-mono text-xs sm:text-caption shrink-0 self-start sm:self-auto">
                      {log.timestamp}
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 sm:p-6 text-center text-body text-[#6B7280] bg-[#F9FAFB] rounded-btn border border-dashed border-[#E5E7EB]">
                  No recent audit logs recorded.
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
