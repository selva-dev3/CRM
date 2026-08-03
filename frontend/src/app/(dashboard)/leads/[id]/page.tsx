'use client';

import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Building2,
  Mail,
  Phone,
  Globe,
  MapPin,
  UserCheck,
  Calendar,
  Pencil,
  Trash2,
  Loader2,
  AlertCircle,
  Briefcase,
  ShieldCheck,
  Building,
  Activity,
  ChevronRight
} from 'lucide-react';
import { Button, Card, Badge, Alert, AlertDescription } from '@/components/ui';
import { useLeadQuery, useDeleteLeadMutation } from '@/lib/api/leads';
import { useOrganizationsQuery } from '@/lib/api/organizations';

export default function LeadDetailPage() {
  const params = useParams();
  const router = useRouter();
  const leadId = (params?.id as string) || '';

  const { data: lead, isLoading, isError, error } = useLeadQuery(leadId);
  const { data: organizations = [] } = useOrganizationsQuery();
  const deleteLeadMutation = useDeleteLeadMutation();
  const [isDeleting, setIsDeleting] = React.useState(false);

  // Helper to resolve org name if ID matches
  const orgName = React.useMemo(() => {
    if (!lead?.organization_id) return 'Enterprise Organization';
    const found = organizations.find((o) => o.id === lead.organization_id);
    return found ? found.name : 'Enterprise Organization';
  }, [lead, organizations]);

  const handleDelete = async () => {
    if (!lead) return;
    if (confirm(`Are you sure you want to delete lead "${lead.contact_name}"?`)) {
      try {
        setIsDeleting(true);
        await deleteLeadMutation.mutateAsync(lead.id);
        router.push('/leads');
      } catch (err) {
        alert('Failed to delete lead.');
        setIsDeleting(false);
      }
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[450px] gap-3 text-slate-600">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
        <p className="text-sm font-bold text-slate-700">Loading Lead Information...</p>
      </div>
    );
  }

  if (isError || !lead) {
    return (
      <div className="w-full max-w-4xl mx-auto space-y-4 pt-4 text-black">
        <Link
          href="/leads"
          className="inline-flex items-center text-xs font-bold text-indigo-600 hover:text-indigo-800 transition"
        >
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Leads
        </Link>
        <Alert variant="destructive" className="bg-rose-50 border-rose-300 text-rose-950 font-bold">
          <AlertCircle className="h-5 w-5 text-rose-600 mr-2" />
          <AlertDescription className="text-rose-900 font-bold">
            Unable to locate lead record. {error?.message || 'The requested lead does not exist.'}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="w-full space-y-6 text-black pb-16 px-1 sm:px-2">
      {/* Breadcrumb Navigation */}
      <nav className="flex items-center gap-2 text-xs font-bold text-slate-700">
        <Link href="/leads" className="hover:text-indigo-600 transition flex items-center gap-1">
          <ArrowLeft className="w-3.5 h-3.5" /> Leads
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
        <span className="text-slate-900 font-black truncate max-w-[200px] sm:max-w-none">
          {lead.contact_name}
        </span>
      </nav>

      {/* Header Banner */}
      <div className="bg-white border border-slate-200 shadow-sm rounded-2xl p-5 sm:p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-5">
        <div className="flex items-start sm:items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-indigo-600 flex items-center justify-center text-white font-black text-xl shadow-md shrink-0">
            {lead.contact_name ? lead.contact_name.charAt(0).toUpperCase() : 'L'}
          </div>
          <div className="space-y-1">
            <div className="flex items-center flex-wrap gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-black text-slate-950 tracking-tight">
                {lead.contact_name}
              </h1>
              <span className="px-2.5 py-0.5 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 font-bold text-xs">
                {lead.status}
              </span>
            </div>
            <p className="text-sm font-bold text-slate-700 flex items-center gap-2 flex-wrap">
              <span>{lead.title}</span>
              <span className="text-slate-300">•</span>
              <span className="text-indigo-600 font-black">{lead.company}</span>
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3 shrink-0">
          <Link href="/leads">
            <Button variant="outline" size="sm" className="border-slate-300 text-slate-900 font-bold hover:bg-slate-100 text-xs px-4 h-9">
              <Pencil className="w-3.5 h-3.5 mr-1.5" /> Edit Lead
            </Button>
          </Link>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={handleDelete}
            disabled={isDeleting}
            className="bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs px-4 h-9 shadow-xs"
          >
            {isDeleting ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5 mr-1.5" />}
            Delete Lead
          </Button>
        </div>
      </div>

      {/* Main Responsive Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 Cols wide on desktop) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Card 1: Lead Overview & Contact Info */}
          <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-6">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-sm font-black uppercase tracking-wider text-slate-900 flex items-center gap-2">
                <Briefcase className="w-4 h-4 text-indigo-600" />
                Lead Overview & Contact Info
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">Contact Name</span>
                <p className="text-sm font-black text-slate-900">{lead.contact_name}</p>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">Opportunity Title</span>
                <p className="text-sm font-bold text-slate-900">{lead.title}</p>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">Email Address</span>
                <p className="text-sm font-bold text-indigo-600 flex items-center gap-2">
                  <Mail className="w-4 h-4 text-slate-400 shrink-0" />
                  <a href={`mailto:${lead.email}`} className="hover:underline truncate">{lead.email}</a>
                </p>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">Phone Number</span>
                <p className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <Phone className="w-4 h-4 text-slate-400 shrink-0" />
                  {lead.phone ? <a href={`tel:${lead.phone}`} className="hover:underline">{lead.phone}</a> : <span className="text-slate-400 italic">Not provided</span>}
                </p>
              </div>
            </div>
          </Card>

          {/* Card 2: Company & Industry Information */}
          <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-6">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-sm font-black uppercase tracking-wider text-slate-900 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-indigo-600" />
                Company & Industry Details
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">Company Name</span>
                <p className="text-sm font-black text-slate-900">{lead.company}</p>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">Industry</span>
                <p className="text-sm font-bold text-slate-900">{lead.industry || <span className="text-slate-400 italic">N/A</span>}</p>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">Company Size</span>
                <p className="text-sm font-bold text-slate-900">{lead.company_size || <span className="text-slate-400 italic">N/A</span>}</p>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">Website</span>
                <p className="text-sm font-bold text-indigo-600 flex items-center gap-2">
                  <Globe className="w-4 h-4 text-slate-400 shrink-0" />
                  {lead.website ? (
                    <a href={lead.website.startsWith('http') ? lead.website : `https://${lead.website}`} target="_blank" rel="noreferrer" className="hover:underline truncate">
                      {lead.website}
                    </a>
                  ) : (
                    <span className="text-slate-400 italic">N/A</span>
                  )}
                </p>
              </div>
            </div>
          </Card>

          {/* Card 3: Address & Location */}
          <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-6">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-sm font-black uppercase tracking-wider text-slate-900 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-indigo-600" />
                Address & Location
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="sm:col-span-2 space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">Street Address</span>
                <p className="text-sm font-bold text-slate-900">{lead.address || <span className="text-slate-400 italic">Not provided</span>}</p>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">City</span>
                <p className="text-sm font-bold text-slate-900">{lead.city || <span className="text-slate-400 italic">N/A</span>}</p>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">State</span>
                <p className="text-sm font-bold text-slate-900">{lead.state || <span className="text-slate-400 italic">N/A</span>}</p>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">Country</span>
                <p className="text-sm font-bold text-slate-900">{lead.country || <span className="text-slate-400 italic">N/A</span>}</p>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-black uppercase text-slate-800 tracking-wider">Postal Code</span>
                <p className="text-sm font-bold text-slate-900">{lead.postal_code || <span className="text-slate-400 italic">N/A</span>}</p>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Column (Sidebar metrics on desktop) */}
        <div className="space-y-6">
          {/* Card 4: Qualification & Engagement Score */}
          <Card className="p-6 bg-slate-900 text-white rounded-2xl shadow-sm space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="text-xs font-black uppercase tracking-wider text-indigo-300 flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-emerald-400" /> Qualification Score
              </span>
              <span className="text-2xl font-black text-white">{lead.score ?? 75}/100</span>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs font-bold text-slate-300">
                <span>Engagement Health</span>
                <span>{lead.score ?? 75}%</span>
              </div>
              <div className="w-full h-2.5 rounded-full bg-slate-950 overflow-hidden border border-slate-800">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 to-emerald-400 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, lead.score ?? 75))}%` }}
                />
              </div>
            </div>

            <div className="pt-2 grid grid-cols-2 gap-3 border-t border-slate-800 text-xs">
              <div>
                <span className="block text-[10px] font-black uppercase text-slate-400">Current Stage</span>
                <span className="inline-block mt-1 px-2.5 py-0.5 rounded-md bg-indigo-900/60 border border-indigo-700 text-indigo-200 font-bold">
                  {lead.status}
                </span>
              </div>
              <div>
                <span className="block text-[10px] font-black uppercase text-slate-400">Lead Source</span>
                <span className="inline-block mt-1 px-2.5 py-0.5 rounded-md bg-slate-800 border border-slate-700 text-slate-200 font-bold">
                  {lead.source}
                </span>
              </div>
            </div>
          </Card>

          {/* Card 5: System & Assignment Information */}
          <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-5">
            <h2 className="text-xs font-black uppercase tracking-wider text-slate-900 border-b border-slate-100 pb-3 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-indigo-600" /> Account & Assignment
            </h2>

            <div className="space-y-4 text-xs font-bold text-slate-700">
              <div className="flex items-center justify-between">
                <span className="text-slate-800 font-black flex items-center gap-1.5">
                  <Building className="w-3.5 h-3.5 text-slate-400" /> Organization
                </span>
                <span className="text-slate-900 font-black text-right max-w-[160px] truncate">{orgName}</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-slate-800 font-black flex items-center gap-1.5">
                  <UserCheck className="w-3.5 h-3.5 text-slate-400" /> Assigned To
                </span>
                <span className="text-indigo-600 font-black">{lead.assigned_to || 'Unassigned'}</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-slate-800 font-black flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" /> Created Date
                </span>
                <span className="text-slate-900">{lead.created_at ? new Date(lead.created_at).toLocaleDateString() : 'N/A'}</span>
              </div>

              <div className="flex items-center justify-between border-t border-slate-100 pt-3">
                <span className="text-slate-800 font-black">Lead Record State</span>
                <span className={lead.is_archived ? 'text-amber-600 font-black' : 'text-emerald-600 font-black'}>
                  {lead.is_archived ? 'Archived' : 'Active'}
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
