'use client';

import React, { useState, useMemo } from 'react';
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
  ChevronRight,
  X,
  CheckCircle2,
  Plus,
  FileText,
  CheckSquare,
  Send,
  PhoneCall,
  Paperclip,
  Zap,
  Archive,
  RefreshCw,
  Award,
  ArrowRightLeft,
  Download,
  Upload
} from 'lucide-react';
import { Button, Card, Label, Input, Badge, Alert, AlertDescription } from '@/components/ui';
import {
  useLeadQuery,
  useCreateLeadMutation,
  useUpdateLeadMutation,
  useDeleteLeadMutation,
  useLeadNotesQuery,
  useLeadTasksQuery,
  useLeadEmailsQuery,
  useLeadCallsQuery,
  useLeadDocumentsQuery,
  addLeadNoteApi,
  createLeadTaskApi,
  sendLeadEmailApi,
  logLeadCallApi,
  uploadLeadDocumentApi,
  recalculateLeadScoreApi,
  convertLeadApi,
  assignLeadApi,
  archiveLeadApi,
  unarchiveLeadApi,
  Lead
} from '@/lib/api/leads';
import { useOrganizationsQuery } from '@/lib/api/organizations';
import { useCompaniesQuery } from '@/lib/api/companies';
import { useUsersQuery } from '@/lib/api/users';
import { useQueryClient } from '@tanstack/react-query';
import { getSessionToken } from '@/lib/api-client';

export default function LeadDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const leadId = (params?.id as string) || '';

  // Active Tab State
  const [activeTab, setActiveTab] = useState<'overview' | 'notes' | 'tasks' | 'emails' | 'calls' | 'documents' | 'actions'>('overview');

  // Queries
  const { data: lead, isLoading, isError, error, refetch } = useLeadQuery(leadId);
  const { data: organizations = [], isLoading: isOrgsLoading } = useOrganizationsQuery();
  const { data: companies = [], isLoading: isCompaniesLoading } = useCompaniesQuery();
  const { data: users = [], isLoading: isUsersLoading } = useUsersQuery(1, 100);

  // Sub-resource Queries
  const { data: notes = [], refetch: refetchNotes, isLoading: isNotesLoading } = useLeadNotesQuery(leadId);
  const { data: tasks = [], refetch: refetchTasks, isLoading: isTasksLoading } = useLeadTasksQuery(leadId);
  const { data: emails = [], refetch: refetchEmails, isLoading: isEmailsLoading } = useLeadEmailsQuery(leadId);
  const { data: calls = [], refetch: refetchCalls, isLoading: isCallsLoading } = useLeadCallsQuery(leadId);
  const { data: documents = [], refetch: refetchDocuments, isLoading: isDocsLoading } = useLeadDocumentsQuery(leadId);

  // Lead Mutations
  const createLeadMutation = useCreateLeadMutation();
  const updateLeadMutation = useUpdateLeadMutation();
  const deleteLeadMutation = useDeleteLeadMutation();

  // Banners & Modals State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Sub-resource Modal Trigger States
  const [isNoteModalOpen, setIsNoteModalOpen] = useState(false);
  const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
  const [isEmailModalOpen, setIsEmailModalOpen] = useState(false);
  const [isCallModalOpen, setIsCallModalOpen] = useState(false);
  const [isDocModalOpen, setIsDocModalOpen] = useState(false);

  // Form Inputs
  const [newNote, setNewNote] = useState('');
  const [isAddingNote, setIsAddingNote] = useState(false);

  const [taskTitle, setTaskTitle] = useState('');
  const [taskDesc, setTaskDesc] = useState('');
  const [taskPriority, setTaskPriority] = useState('Medium');
  const [isCreatingTask, setIsCreatingTask] = useState(false);

  const [emailTo, setEmailTo] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [emailBody, setEmailBody] = useState('');
  const [isSendingEmail, setIsSendingEmail] = useState(false);

  const [callType, setCallType] = useState('Outbound');
  const [callDuration, setCallDuration] = useState('180');
  const [callNotes, setCallNotes] = useState('');
  const [isLoggingCall, setIsLoggingCall] = useState(false);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploadingDoc, setIsUploadingDoc] = useState(false);

  const [isRecalculatingScore, setIsRecalculatingScore] = useState(false);
  const [isConverting, setIsConverting] = useState(false);
  const [selectedAssignUser, setSelectedAssignUser] = useState('');
  const [isAssigning, setIsAssigning] = useState(false);
  const [isArchiving, setIsArchiving] = useState(false);

  // Lead Create/Edit Form State
  const [contactName, setContactName] = useState('');
  const [company, setCompany] = useState('');
  const [customCompany, setCustomCompany] = useState('');
  const [title, setTitle] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [website, setWebsite] = useState('');
  const [industry, setIndustry] = useState('');
  const [companySize, setCompanySize] = useState('');
  const [country, setCountry] = useState('');
  const [stateName, setStateName] = useState('');
  const [city, setCity] = useState('');
  const [address, setAddress] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [status, setStatus] = useState('New');
  const [source, setSource] = useState('Website');
  const [organizationId, setOrganizationId] = useState('');
  const [score, setScore] = useState<number>(75);
  const [assignedTo, setAssignedTo] = useState<string>('');
  const [isArchived, setIsArchived] = useState<boolean>(false);

  const orgName = useMemo(() => {
    if (!lead?.organization_id) return 'Enterprise Organization';
    const found = organizations.find((o) => o.id === lead.organization_id);
    return found ? found.name : 'Enterprise Organization';
  }, [lead, organizations]);

  const formatFileSize = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const resetForm = () => {
    setContactName('');
    setCompany(companies.length > 0 ? companies[0].name : '');
    setCustomCompany('');
    setTitle('');
    setEmail('');
    setPhone('');
    setWebsite('');
    setIndustry('');
    setCompanySize('');
    setCountry('');
    setStateName('');
    setCity('');
    setAddress('');
    setPostalCode('');
    setStatus('New');
    setSource('Website');
    setOrganizationId(organizations.length > 0 ? organizations[0].id : 'org-1');
    setScore(75);
    setAssignedTo('');
    setIsArchived(false);
    setErrorMessage(null);
  };

  const handleOpenCreateModal = () => {
    setIsEditMode(false);
    resetForm();
    if (organizations.length > 0) setOrganizationId(organizations[0].id);
    if (companies.length > 0) setCompany(companies[0].name);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = () => {
    if (!lead) return;
    setIsEditMode(true);
    setContactName(lead.contact_name || '');
    setCompany(lead.company || '');
    setCustomCompany('');
    setTitle(lead.title || '');
    setEmail(lead.email || '');
    setPhone(lead.phone || '');
    setWebsite(lead.website || '');
    setIndustry(lead.industry || '');
    setCompanySize(lead.company_size || '');
    setCountry(lead.country || '');
    setStateName(lead.state || '');
    setCity(lead.city || '');
    setAddress(lead.address || '');
    setPostalCode(lead.postal_code || '');
    setStatus(lead.status || 'New');
    setSource(lead.source || 'Website');
    setOrganizationId(lead.organization_id || (organizations[0]?.id ?? 'org-1'));
    setScore(lead.score ?? 75);
    setAssignedTo(lead.assigned_to || '');
    setIsArchived(lead.is_archived ?? false);
    setErrorMessage(null);
    setIsModalOpen(true);
  };

  const handleSubmitForm = async (e: React.FormEvent) => {
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
        website: website.trim() || undefined,
        industry: industry.trim() || undefined,
        company_size: companySize || undefined,
        country: country.trim() || undefined,
        state: stateName.trim() || undefined,
        city: city.trim() || undefined,
        address: address.trim() || undefined,
        postal_code: postalCode.trim() || undefined,
        status,
        source,
        score: Number(score) || 75,
        assigned_to: assignedTo.trim() || undefined,
        is_archived: isArchived,
        organization_id: organizationId || (organizations[0]?.id ?? 'org-1'),
      };

      if (isEditMode && lead) {
        await updateLeadMutation.mutateAsync({ id: lead.id, payload });
        await queryClient.invalidateQueries({ queryKey: ['lead', lead.id] });
        await refetch();
        setSuccessMessage('Lead updated successfully!');
      } else {
        const newLead = await createLeadMutation.mutateAsync(payload);
        setSuccessMessage(`Lead "${newLead.contact_name}" created successfully! Redirecting...`);
        setTimeout(() => {
          router.push(`/leads/${newLead.id}`);
        }, 1000);
      }

      setIsModalOpen(false);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to save lead.');
    }
  };

  const handleConfirmDelete = async () => {
    if (!lead) return;
    try {
      await deleteLeadMutation.mutateAsync(lead.id);
      setIsDeleteModalOpen(false);
      router.push('/leads');
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to delete lead.');
    }
  };

  // Sub-resource Modal Submissions
  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNote.trim()) return;
    try {
      setIsAddingNote(true);
      await addLeadNoteApi(leadId, newNote.trim());
      setNewNote('');
      setIsNoteModalOpen(false);
      await refetchNotes();
      setSuccessMessage('Note added successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to add note.');
    } finally {
      setIsAddingNote(false);
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskTitle.trim()) return;
    try {
      setIsCreatingTask(true);
      await createLeadTaskApi(leadId, { title: taskTitle.trim(), description: taskDesc.trim(), priority: taskPriority });
      setTaskTitle('');
      setTaskDesc('');
      setIsTaskModalOpen(false);
      await refetchTasks();
      setSuccessMessage('Task created successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to create task.');
    } finally {
      setIsCreatingTask(false);
    }
  };

  const handleSendEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailSubject.trim()) return;
    try {
      setIsSendingEmail(true);
      await sendLeadEmailApi(leadId, { to: [emailTo || lead?.email || 'lead@example.com'], subject: emailSubject.trim(), body: emailBody.trim() });
      setEmailSubject('');
      setEmailBody('');
      setIsEmailModalOpen(false);
      await refetchEmails();
      setSuccessMessage('Email sent successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to send email.');
    } finally {
      setIsSendingEmail(false);
    }
  };

  const handleLogCall = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsLoggingCall(true);
      await logLeadCallApi(leadId, { call_type: callType, duration_seconds: Number(callDuration) || 180, notes: callNotes.trim() });
      setCallNotes('');
      setIsCallModalOpen(false);
      await refetchCalls();
      setSuccessMessage('Call record logged successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to log call.');
    } finally {
      setIsLoggingCall(false);
    }
  };

  const handleUploadDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    try {
      setIsUploadingDoc(true);
      await uploadLeadDocumentApi(leadId, selectedFile);
      setSelectedFile(null);
      setIsDocModalOpen(false);
      await refetchDocuments();
      setSuccessMessage('Document attached successfully to MinIO S3!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to upload document.');
    } finally {
      setIsUploadingDoc(false);
    }
  };

  const handleRecalculateScore = async () => {
    try {
      setIsRecalculatingScore(true);
      await recalculateLeadScoreApi(leadId);
      await refetch();
      setSuccessMessage('AI Lead score recalculated!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage('Failed to recalculate score.');
    } finally {
      setIsRecalculatingScore(false);
    }
  };

  const handleConvertLead = async () => {
    try {
      setIsConverting(true);
      await convertLeadApi(leadId, { create_deal: true, deal_title: `${lead?.contact_name} Deal` });
      await refetch();
      setSuccessMessage('Lead converted to Deal, Contact, and Company!');
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage('Failed to convert lead.');
    } finally {
      setIsConverting(false);
    }
  };

  const handleAssignLead = async () => {
    if (!selectedAssignUser) return;
    try {
      setIsAssigning(true);
      await assignLeadApi(leadId, selectedAssignUser);
      await refetch();
      setSuccessMessage(`Lead assigned to user successfully!`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage('Failed to assign lead.');
    } finally {
      setIsAssigning(false);
    }
  };

  const handleToggleArchive = async () => {
    try {
      setIsArchiving(true);
      if (lead?.is_archived) {
        await unarchiveLeadApi(leadId);
        setSuccessMessage('Lead unarchived successfully!');
      } else {
        await archiveLeadApi(leadId);
        setSuccessMessage('Lead archived successfully!');
      }
      await refetch();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage('Failed to change archive status.');
    } finally {
      setIsArchiving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[450px] gap-3 text-slate-600">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
        <p className="text-sm font-bold text-slate-700">Loading Lead Details...</p>
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

      {/* Success Banner */}
      {successMessage && (
        <Alert variant="default" className="bg-emerald-50 border-emerald-300 text-emerald-950 font-bold animate-in fade-in-50">
          <CheckCircle2 className="h-4 w-4 text-emerald-600 mr-2" />
          <AlertDescription className="text-emerald-900 font-bold">
            {successMessage}
          </AlertDescription>
        </Alert>
      )}

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

        {/* Header Actions */}
        <div className="flex items-center gap-2.5 shrink-0 flex-wrap">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleOpenEditModal}
            className="border-slate-300 text-slate-900 font-bold hover:bg-slate-100 text-xs px-4 h-9 cursor-pointer"
          >
            <Pencil className="w-3.5 h-3.5 mr-1.5" /> Edit Lead
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => setIsDeleteModalOpen(true)}
            className="bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs px-4 h-9 shadow-xs cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Delete Lead
          </Button>
        </div>
      </div>

      {/* Enterprise Tabbed Interface Header */}
      <div className="border-b border-slate-200 overflow-x-auto scrollbar-none">
        <nav className="flex space-x-2 min-w-max pb-1">
          {[
            { id: 'overview', label: 'Overview & Details', icon: Briefcase },
            { id: 'notes', label: `Notes (${notes.length})`, icon: FileText },
            { id: 'tasks', label: `Tasks (${tasks.length})`, icon: CheckSquare },
            { id: 'emails', label: `Emails (${emails.length})`, icon: Send },
            { id: 'calls', label: `Calls (${calls.length})`, icon: PhoneCall },
            { id: 'documents', label: `Documents (${documents.length})`, icon: Paperclip },
            { id: 'actions', label: 'Actions & Convert', icon: Zap },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs font-black rounded-xl transition cursor-pointer border ${
                  isActive
                    ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                    : 'bg-white text-slate-700 hover:bg-slate-100 border-slate-200'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-slate-500'}`} />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* TAB CONTENTS */}

      {/* 1. OVERVIEW & DETAILS TAB */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
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

          <div className="space-y-6">
            <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-5">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <span className="text-xs font-black uppercase tracking-wider text-slate-900 flex items-center gap-1.5">
                  <Activity className="w-4 h-4 text-indigo-600" /> Qualification Score
                </span>
                {(lead.score ?? 75) >= 70 ? (
                  <span className="px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-black text-[11px]">
                    🔥 High Intent
                  </span>
                ) : (lead.score ?? 75) >= 40 ? (
                  <span className="px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-black text-[11px]">
                    ⚡ Warm Lead
                  </span>
                ) : (
                  <span className="px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 font-black text-[11px]">
                    ❄️ Cold Lead
                  </span>
                )}
              </div>

              <div className="flex items-baseline justify-between">
                <div>
                  <div className="text-3xl font-black text-slate-950 tracking-tight">
                    {lead.score ?? 75}
                    <span className="text-sm font-bold text-slate-600 ml-1">/ 100</span>
                  </div>
                  <p className="text-[11px] font-bold text-slate-600 mt-0.5">Engagement & Conversion Potential</p>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-bold text-slate-700">
                  <span>Engagement Health</span>
                  <span className="font-black text-slate-900">{lead.score ?? 75}%</span>
                </div>
                <div className="w-full h-3 rounded-full bg-slate-100 overflow-hidden border border-slate-200 p-0.5">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-500 rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, Math.max(0, lead.score ?? 75))}%` }}
                  />
                </div>
              </div>

              <div className="pt-2 grid grid-cols-2 gap-3 border-t border-slate-100 text-xs">
                <div className="space-y-1">
                  <span className="block text-[10px] font-black uppercase text-slate-800">Current Stage</span>
                  <span className="inline-block px-2.5 py-0.5 rounded-md bg-indigo-50 border border-indigo-200 text-indigo-700 font-black">
                    {lead.status}
                  </span>
                </div>
                <div className="space-y-1">
                  <span className="block text-[10px] font-black uppercase text-slate-800">Lead Source</span>
                  <span className="inline-block px-2.5 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-800 font-bold">
                    {lead.source}
                  </span>
                </div>
              </div>
            </Card>

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
      )}

      {/* 2. NOTES TAB */}
      {activeTab === 'notes' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-sm font-black uppercase tracking-wider text-slate-900 flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-600" /> Lead Notes ({notes.length})
              </h3>
              <p className="text-xs font-bold text-slate-500 mt-0.5">Notes attached to lead {lead.contact_name}</p>
            </div>
            <Button
              type="button"
              onClick={() => setIsNoteModalOpen(true)}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-4 h-9 shadow-xs cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" /> + Add Note
            </Button>
          </div>

          {isNotesLoading ? (
            <div className="p-8 text-center text-slate-500 text-xs font-bold flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-600" /> Loading notes...
            </div>
          ) : notes.length === 0 ? (
            <div className="p-8 text-center bg-slate-50 border border-dashed border-slate-200 rounded-xl space-y-2">
              <FileText className="w-8 h-8 text-slate-300 mx-auto" />
              <p className="text-xs font-bold text-slate-600">No notes attached yet.</p>
              <p className="text-[11px] text-slate-400">Click "+ Add Note" above to attach a note.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-black uppercase text-slate-700 tracking-wider">
                    <th className="py-3 px-4">Note Content</th>
                    <th className="py-3 px-4">Author / Created By</th>
                    <th className="py-3 px-4">Created Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {notes.map((n) => (
                    <tr key={n.id} className="hover:bg-slate-50 transition">
                      <td className="py-3.5 px-4 font-bold text-slate-900 max-w-md">{n.content}</td>
                      <td className="py-3.5 px-4 font-bold text-indigo-600">{n.created_by || 'System User'}</td>
                      <td className="py-3.5 px-4 font-bold text-slate-600">{new Date(n.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* 3. TASKS TAB */}
      {activeTab === 'tasks' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-sm font-black uppercase tracking-wider text-slate-900 flex items-center gap-2">
                <CheckSquare className="w-4 h-4 text-indigo-600" /> Assigned Lead Tasks ({tasks.length})
              </h3>
              <p className="text-xs font-bold text-slate-500 mt-0.5">Tasks created for lead {lead.contact_name}</p>
            </div>
            <Button
              type="button"
              onClick={() => setIsTaskModalOpen(true)}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-4 h-9 shadow-xs cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" /> + Create Task
            </Button>
          </div>

          {isTasksLoading ? (
            <div className="p-8 text-center text-slate-500 text-xs font-bold flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-600" /> Loading tasks...
            </div>
          ) : tasks.length === 0 ? (
            <div className="p-8 text-center bg-slate-50 border border-dashed border-slate-200 rounded-xl space-y-2">
              <CheckSquare className="w-8 h-8 text-slate-300 mx-auto" />
              <p className="text-xs font-bold text-slate-600">No tasks created for this lead yet.</p>
              <p className="text-[11px] text-slate-400">Click "+ Create Task" above to assign a new task.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-black uppercase text-slate-700 tracking-wider">
                    <th className="py-3 px-4">Task Title & Description</th>
                    <th className="py-3 px-4">Priority</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Due Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {tasks.map((t) => (
                    <tr key={t.id} className="hover:bg-slate-50 transition">
                      <td className="py-3.5 px-4 space-y-0.5">
                        <div className="font-black text-slate-900">{t.title}</div>
                        {t.description && <div className="text-[11px] font-bold text-slate-500">{t.description}</div>}
                      </td>
                      <td className="py-3.5 px-4 font-bold">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-black ${
                          t.priority === 'High' ? 'bg-rose-50 text-rose-700 border border-rose-200' :
                          t.priority === 'Medium' ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-slate-100 text-slate-700'
                        }`}>
                          {t.priority || 'Medium'}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-bold">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-indigo-50 text-indigo-700 border border-indigo-200">
                          {t.status || 'Pending'}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-bold text-slate-600">{t.due_date ? new Date(t.due_date).toLocaleDateString() : 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* 4. EMAILS TAB */}
      {activeTab === 'emails' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-sm font-black uppercase tracking-wider text-slate-900 flex items-center gap-2">
                <Send className="w-4 h-4 text-indigo-600" /> Email History ({emails.length})
              </h3>
              <p className="text-xs font-bold text-slate-500 mt-0.5">Emails sent to lead {lead.contact_name}</p>
            </div>
            <Button
              type="button"
              onClick={() => {
                setEmailTo(lead.email);
                setIsEmailModalOpen(true);
              }}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-4 h-9 shadow-xs cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" /> + Send Email
            </Button>
          </div>

          {isEmailsLoading ? (
            <div className="p-8 text-center text-slate-500 text-xs font-bold flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-600" /> Loading emails...
            </div>
          ) : emails.length === 0 ? (
            <div className="p-8 text-center bg-slate-50 border border-dashed border-slate-200 rounded-xl space-y-2">
              <Send className="w-8 h-8 text-slate-300 mx-auto" />
              <p className="text-xs font-bold text-slate-600">No email communications logged yet.</p>
              <p className="text-[11px] text-slate-400">Click "+ Send Email" above to send an email.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-black uppercase text-slate-700 tracking-wider">
                    <th className="py-3 px-4">Subject Line</th>
                    <th className="py-3 px-4">Recipient (To)</th>
                    <th className="py-3 px-4">Sender (From)</th>
                    <th className="py-3 px-4">Sent Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {emails.map((e) => (
                    <tr key={e.id} className="hover:bg-slate-50 transition">
                      <td className="py-3.5 px-4 font-black text-slate-900">{e.subject}</td>
                      <td className="py-3.5 px-4 font-bold text-indigo-600">{e.to.join(', ')}</td>
                      <td className="py-3.5 px-4 font-bold text-slate-600">{e.from_email}</td>
                      <td className="py-3.5 px-4 font-bold text-slate-600">{new Date(e.sent_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* 5. CALLS TAB */}
      {activeTab === 'calls' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-sm font-black uppercase tracking-wider text-slate-900 flex items-center gap-2">
                <PhoneCall className="w-4 h-4 text-indigo-600" /> Phone Call Logs ({calls.length})
              </h3>
              <p className="text-xs font-bold text-slate-500 mt-0.5">Call history logged for lead {lead.contact_name}</p>
            </div>
            <Button
              type="button"
              onClick={() => setIsCallModalOpen(true)}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-4 h-9 shadow-xs cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" /> + Log Call
            </Button>
          </div>

          {isCallsLoading ? (
            <div className="p-8 text-center text-slate-500 text-xs font-bold flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-600" /> Loading call logs...
            </div>
          ) : calls.length === 0 ? (
            <div className="p-8 text-center bg-slate-50 border border-dashed border-slate-200 rounded-xl space-y-2">
              <PhoneCall className="w-8 h-8 text-slate-300 mx-auto" />
              <p className="text-xs font-bold text-slate-600">No call logs recorded yet.</p>
              <p className="text-[11px] text-slate-400">Click "+ Log Call" above to record a phone conversation.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-black uppercase text-slate-700 tracking-wider">
                    <th className="py-3 px-4">Direction</th>
                    <th className="py-3 px-4">Duration</th>
                    <th className="py-3 px-4">Call Notes</th>
                    <th className="py-3 px-4">Date & Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {calls.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50 transition">
                      <td className="py-3.5 px-4 font-bold">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-black ${
                          c.call_type === 'Outbound' ? 'bg-indigo-50 text-indigo-700 border border-indigo-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        }`}>
                          {c.call_type} Call
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-black text-slate-900">{Math.floor(c.duration_seconds / 60)}m {c.duration_seconds % 60}s</td>
                      <td className="py-3.5 px-4 font-bold text-slate-700">{c.notes || 'N/A'}</td>
                      <td className="py-3.5 px-4 font-bold text-slate-600">{new Date(c.timestamp).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* 6. DOCUMENTS TAB */}
      {activeTab === 'documents' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-sm font-black uppercase tracking-wider text-slate-900 flex items-center gap-2">
                <Paperclip className="w-4 h-4 text-indigo-600" /> Attached Documents ({documents.length})
              </h3>
              <p className="text-xs font-bold text-slate-500 mt-0.5">Files uploaded to S3 storage for lead {lead.contact_name}</p>
            </div>
            <Button
              type="button"
              onClick={() => setIsDocModalOpen(true)}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-4 h-9 shadow-xs cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" /> + Upload Document
            </Button>
          </div>

          {isDocsLoading ? (
            <div className="p-8 text-center text-slate-500 text-xs font-bold flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-600" /> Loading documents...
            </div>
          ) : documents.length === 0 ? (
            <div className="p-8 text-center bg-slate-50 border border-dashed border-slate-200 rounded-xl space-y-2">
              <Paperclip className="w-8 h-8 text-slate-300 mx-auto" />
              <p className="text-xs font-bold text-slate-600">No documents uploaded yet.</p>
              <p className="text-[11px] text-slate-400">Click "+ Upload Document" above to attach a file.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-black uppercase text-slate-700 tracking-wider">
                    <th className="py-3 px-4">Filename</th>
                    <th className="py-3 px-4">File Size</th>
                    <th className="py-3 px-4">MIME Type</th>
                    <th className="py-3 px-4">Uploaded Date</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {documents.map((d) => (
                    <tr key={d.id} className="hover:bg-slate-50 transition">
                      <td className="py-3.5 px-4 font-black text-slate-900 flex items-center gap-2">
                        <Paperclip className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
                        <span className="truncate max-w-[200px]">{d.filename}</span>
                      </td>
                      <td className="py-3.5 px-4 font-bold text-slate-700">{formatFileSize(d.file_size)}</td>
                      <td className="py-3.5 px-4 font-bold text-slate-600">{d.mime_type || 'application/pdf'}</td>
                      <td className="py-3.5 px-4 font-bold text-slate-600">{new Date(d.uploaded_at).toLocaleString()}</td>
                      <td className="py-3.5 px-4 text-right">
                        {d.download_url && (
                          <a
                            href={
                              d.download_url.startsWith('http') && !d.download_url.includes('.internal')
                                ? d.download_url
                                : `${(process.env.NEXT_PUBLIC_API_URL || 'https://crm-dev3.up.railway.app/api/v1').replace(/\/$/, '')}/leads/${leadId}/documents/${d.id}/download${
                                    getSessionToken() ? `?token=${encodeURIComponent(getSessionToken() || '')}` : ''
                                  }`
                            }
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center text-xs font-black text-indigo-600 hover:text-indigo-800 hover:underline"
                          >
                            <Download className="w-3 h-3 mr-1" /> Download
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* 7. ACTIONS & CONVERT TAB */}
      {activeTab === 'actions' && (
        <div className="space-y-6">
          <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-black text-slate-950 flex items-center gap-2">
                  <Award className="w-4 h-4 text-indigo-600" /> Recalculate AI Qualification Score
                </h3>
                <p className="text-xs font-bold text-slate-600">Re-evaluates lead metrics and updates engagement score</p>
              </div>
              <Button type="button" onClick={handleRecalculateScore} disabled={isRecalculatingScore} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-4 cursor-pointer">
                {isRecalculatingScore ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
                Recalculate AI Score
              </Button>
            </div>
          </Card>

          <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-black text-slate-950 flex items-center gap-2">
                  <ArrowRightLeft className="w-4 h-4 text-emerald-600" /> Convert Lead to Deal, Contact & Company
                </h3>
                <p className="text-xs font-bold text-slate-600">Converts qualified sales lead into deal pipeline</p>
              </div>
              <Button type="button" onClick={handleConvertLead} disabled={isConverting} className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs px-4 cursor-pointer">
                {isConverting ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <ArrowRightLeft className="w-3.5 h-3.5 mr-1.5" />}
                Convert Lead
              </Button>
            </div>
          </Card>

          <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-4">
            <h3 className="text-sm font-black text-slate-950 flex items-center gap-2 border-b border-slate-100 pb-3">
              <UserCheck className="w-4 h-4 text-indigo-600" /> Assign Lead to Sales Representative
            </h3>
            <div className="flex items-center gap-3 flex-wrap">
              <select value={selectedAssignUser} onChange={(e) => setSelectedAssignUser(e.target.value)} className="w-full sm:w-72 px-3 py-2 border border-slate-300 rounded-lg bg-slate-50 text-xs font-bold text-black">
                <option value="">Select Sales Rep User...</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>{u.name} ({u.role})</option>
                ))}
              </select>
              <Button type="button" onClick={handleAssignLead} disabled={isAssigning || !selectedAssignUser} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-4 cursor-pointer">
                {isAssigning ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : 'Assign Lead'}
              </Button>
            </div>
          </Card>

          <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-black text-slate-950 flex items-center gap-2">
                  <Archive className="w-4 h-4 text-amber-600" /> Archive / Unarchive Lead
                </h3>
                <p className="text-xs font-bold text-slate-600">Toggle lead record active or archived state</p>
              </div>
              <Button type="button" onClick={handleToggleArchive} disabled={isArchiving} className="bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs px-4 cursor-pointer">
                {isArchiving ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Archive className="w-3.5 h-3.5 mr-1.5" />}
                {lead.is_archived ? 'Unarchive Lead' : 'Archive Lead'}
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* MODAL 1: ADD NOTE MODAL */}
      {isNoteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-lg bg-white rounded-2xl border border-slate-300 shadow-2xl overflow-hidden text-black">
            <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                  <FileText className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-black text-black">Add Lead Note</h3>
                  <p className="text-xs font-bold text-slate-600">Attach a note for {lead.contact_name}</p>
                </div>
              </div>
              <button type="button" onClick={() => setIsNoteModalOpen(false)} className="p-1.5 rounded-lg text-slate-600 hover:bg-slate-200 transition cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleAddNote} className="p-6 space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Note Content *</Label>
                <textarea
                  required
                  rows={4}
                  placeholder="Type note regarding conversation, follow-up, or lead requirement..."
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div className="pt-2 flex items-center justify-end gap-3 border-t border-slate-100">
                <Button type="button" variant="outline" onClick={() => setIsNoteModalOpen(false)} className="border-slate-300 text-black font-bold text-xs">
                  Cancel
                </Button>
                <Button type="submit" disabled={isAddingNote} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-5 cursor-pointer">
                  {isAddingNote ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : 'Save Note'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: CREATE TASK MODAL */}
      {isTaskModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-lg bg-white rounded-2xl border border-slate-300 shadow-2xl overflow-hidden text-black">
            <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                  <CheckSquare className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-black text-black">Create Lead Task</h3>
                  <p className="text-xs font-bold text-slate-600">Assign a task for {lead.contact_name}</p>
                </div>
              </div>
              <button type="button" onClick={() => setIsTaskModalOpen(false)} className="p-1.5 rounded-lg text-slate-600 hover:bg-slate-200 transition cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateTask} className="p-6 space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Task Title *</Label>
                <Input required placeholder="Schedule follow-up call" value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} className="bg-slate-50 border-slate-300 text-xs font-bold text-black" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Description</Label>
                <Input placeholder="Prepare pricing quotation and proposal deck" value={taskDesc} onChange={(e) => setTaskDesc(e.target.value)} className="bg-slate-50 border-slate-300 text-xs font-bold text-black" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Priority</Label>
                <select value={taskPriority} onChange={(e) => setTaskPriority(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-slate-50 text-xs font-bold text-black">
                  <option value="High">High</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </select>
              </div>
              <div className="pt-2 flex items-center justify-end gap-3 border-t border-slate-100">
                <Button type="button" variant="outline" onClick={() => setIsTaskModalOpen(false)} className="border-slate-300 text-black font-bold text-xs">
                  Cancel
                </Button>
                <Button type="submit" disabled={isCreatingTask} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-5 cursor-pointer">
                  {isCreatingTask ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : 'Create Task'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: SEND EMAIL MODAL */}
      {isEmailModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-lg bg-white rounded-2xl border border-slate-300 shadow-2xl overflow-hidden text-black">
            <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                  <Send className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-black text-black">Send Email</h3>
                  <p className="text-xs font-bold text-slate-600">Send email to {lead.contact_name}</p>
                </div>
              </div>
              <button type="button" onClick={() => setIsEmailModalOpen(false)} className="p-1.5 rounded-lg text-slate-600 hover:bg-slate-200 transition cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSendEmail} className="p-6 space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Recipient Email</Label>
                <Input type="email" value={emailTo} onChange={(e) => setEmailTo(e.target.value)} className="bg-slate-50 border-slate-300 text-xs font-bold text-black" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Subject Line *</Label>
                <Input required placeholder="Enterprise CRM Proposal & Next Steps" value={emailSubject} onChange={(e) => setEmailSubject(e.target.value)} className="bg-slate-50 border-slate-300 text-xs font-bold text-black" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Email Body</Label>
                <textarea rows={4} placeholder="Hi, following up on our recent demo..." value={emailBody} onChange={(e) => setEmailBody(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-xl bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
              <div className="pt-2 flex items-center justify-end gap-3 border-t border-slate-100">
                <Button type="button" variant="outline" onClick={() => setIsEmailModalOpen(false)} className="border-slate-300 text-black font-bold text-xs">
                  Cancel
                </Button>
                <Button type="submit" disabled={isSendingEmail} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-5 cursor-pointer">
                  {isSendingEmail ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : 'Send Email'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 4: LOG CALL MODAL */}
      {isCallModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-lg bg-white rounded-2xl border border-slate-300 shadow-2xl overflow-hidden text-black">
            <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                  <PhoneCall className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-black text-black">Log Phone Call</h3>
                  <p className="text-xs font-bold text-slate-600">Record call with {lead.contact_name}</p>
                </div>
              </div>
              <button type="button" onClick={() => setIsCallModalOpen(false)} className="p-1.5 rounded-lg text-slate-600 hover:bg-slate-200 transition cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleLogCall} className="p-6 space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Call Direction</Label>
                <select value={callType} onChange={(e) => setCallType(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-slate-50 text-xs font-bold text-black">
                  <option value="Outbound">Outbound Call</option>
                  <option value="Inbound">Inbound Call</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Duration (seconds)</Label>
                <Input type="number" value={callDuration} onChange={(e) => setCallDuration(e.target.value)} className="bg-slate-50 border-slate-300 text-xs font-bold text-black" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Call Notes</Label>
                <Input placeholder="Discussed pricing model and integration timeline..." value={callNotes} onChange={(e) => setCallNotes(e.target.value)} className="bg-slate-50 border-slate-300 text-xs font-bold text-black" />
              </div>
              <div className="pt-2 flex items-center justify-end gap-3 border-t border-slate-100">
                <Button type="button" variant="outline" onClick={() => setIsCallModalOpen(false)} className="border-slate-300 text-black font-bold text-xs">
                  Cancel
                </Button>
                <Button type="submit" disabled={isLoggingCall} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-5 cursor-pointer">
                  {isLoggingCall ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : 'Log Call'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 5: UPLOAD DOCUMENT MODAL */}
      {isDocModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-lg bg-white rounded-2xl border border-slate-300 shadow-2xl overflow-hidden text-black">
            <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                  <Upload className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-black text-black">Upload Lead Document</h3>
                  <p className="text-xs font-bold text-slate-600">Attach file to MinIO S3 for {lead.contact_name}</p>
                </div>
              </div>
              <button type="button" onClick={() => setIsDocModalOpen(false)} className="p-1.5 rounded-lg text-slate-600 hover:bg-slate-200 transition cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleUploadDocument} className="p-6 space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-black text-black">Choose File *</Label>
                <input
                  type="file"
                  required
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
                />
              </div>
              <div className="pt-2 flex items-center justify-end gap-3 border-t border-slate-100">
                <Button type="button" variant="outline" onClick={() => setIsDocModalOpen(false)} className="border-slate-300 text-black font-bold text-xs">
                  Cancel
                </Button>
                <Button type="submit" disabled={isUploadingDoc || !selectedFile} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-5 cursor-pointer">
                  {isUploadingDoc ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : 'Upload File'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CREATE & EDIT LEAD MODAL DIALOG */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-3xl max-h-[90vh] bg-white rounded-2xl border border-slate-300 shadow-2xl overflow-hidden flex flex-col text-black">
            <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                  {isEditMode ? <Pencil className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                </div>
                <div>
                  <h3 className="text-base font-black text-black">
                    {isEditMode ? 'Edit Sales Lead' : 'Create New Sales Lead'}
                  </h3>
                  <p className="text-xs font-bold text-slate-800">
                    {isEditMode ? `Update details for ${lead.contact_name}` : 'Fill lead, company & location details below'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                disabled={createLeadMutation.isPending || updateLeadMutation.isPending}
                className="p-1.5 rounded-lg text-slate-600 hover:bg-slate-200 transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {errorMessage && (
              <div className="px-6 pt-4 shrink-0">
                <Alert variant="destructive" className="bg-rose-50 border-rose-300 text-rose-950 font-bold">
                  <AlertCircle className="h-4 w-4 text-rose-600 mr-2" />
                  <AlertDescription className="text-rose-900 font-bold text-xs">{errorMessage}</AlertDescription>
                </Alert>
              </div>
            )}

            <form onSubmit={handleSubmitForm} className="p-6 space-y-6 overflow-y-auto flex-1">
              <div className="space-y-3">
                <h4 className="text-xs font-black uppercase tracking-wider text-indigo-700 pb-1 border-b border-slate-200">
                  1. Contact Information
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">Contact Name *</Label>
                    <Input
                      required
                      placeholder="e.g. John Doe"
                      value={contactName}
                      onChange={(e) => setContactName(e.target.value)}
                      className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">Email Address *</Label>
                    <Input
                      type="email"
                      required
                      placeholder="john@acme.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">Phone Number</Label>
                    <Input
                      placeholder="+1 (555) 000-0000"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">Opportunity / Lead Title</Label>
                    <Input
                      placeholder="e.g. Enterprise Deal"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-3 pt-2">
                <h4 className="text-xs font-black uppercase tracking-wider text-indigo-700 pb-1 border-b border-slate-200">
                  2. Company & Industry Details
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">Select Company *</Label>
                    <select
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      {companies.map((c) => (
                        <option key={c.id} value={c.name}>
                          {c.name}
                        </option>
                      ))}
                      <option value="other">+ Enter Custom Company Name</option>
                    </select>

                    {company === 'other' && (
                      <Input
                        placeholder="Enter company name"
                        value={customCompany}
                        onChange={(e) => setCustomCompany(e.target.value)}
                        className="bg-white border-indigo-400 text-black font-bold text-xs mt-2"
                      />
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">Website</Label>
                    <Input
                      placeholder="https://company.com"
                      value={website}
                      onChange={(e) => setWebsite(e.target.value)}
                      className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">Industry</Label>
                    <Input
                      placeholder="e.g. Software, Finance"
                      value={industry}
                      onChange={(e) => setIndustry(e.target.value)}
                      className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">Company Size</Label>
                    <select
                      value={companySize}
                      onChange={(e) => setCompanySize(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="">Select Company Size...</option>
                      <option value="1-10">1-10 Employees</option>
                      <option value="11-50">11-50 Employees</option>
                      <option value="51-200">51-200 Employees</option>
                      <option value="201-500">201-500 Employees</option>
                      <option value="501-1000">501-1000 Employees</option>
                      <option value="1000+">1000+ Employees</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="space-y-3 pt-2">
                <h4 className="text-xs font-black uppercase tracking-wider text-indigo-700 pb-1 border-b border-slate-200">
                  3. Address & Location
                </h4>
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">Address</Label>
                    <Input
                      placeholder="Street address, suite, or building"
                      value={address}
                      onChange={(e) => setAddress(e.target.value)}
                      className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                    />
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">City</Label>
                      <Input
                        placeholder="e.g. Chennai"
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">State</Label>
                      <Input
                        placeholder="e.g. TN"
                        value={stateName}
                        onChange={(e) => setStateName(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Country</Label>
                      <Input
                        placeholder="e.g. India"
                        value={country}
                        onChange={(e) => setCountry(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Postal Code</Label>
                      <Input
                        placeholder="600096"
                        value={postalCode}
                        onChange={(e) => setPostalCode(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-3 pt-2">
                <h4 className="text-xs font-black uppercase tracking-wider text-indigo-700 pb-1 border-b border-slate-200">
                  4. Status, Source, Score & Organization
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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

                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">Organization *</Label>
                    <select
                      value={organizationId}
                      onChange={(e) => setOrganizationId(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      {isOrgsLoading ? (
                        <option value="">Loading...</option>
                      ) : (
                        organizations.map((org) => (
                          <option key={org.id} value={org.id}>
                            {org.name}
                          </option>
                        ))
                      )}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1 items-end">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">AI Score (0-100)</Label>
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      placeholder="75"
                      value={score}
                      onChange={(e) => setScore(Number(e.target.value))}
                      className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">Assigned To User</Label>
                    <select
                      value={assignedTo}
                      onChange={(e) => setAssignedTo(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="">Unassigned (None)</option>
                      {isUsersLoading ? (
                        <option value="" disabled>Loading users...</option>
                      ) : (
                        users.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.name} ({u.role})
                          </option>
                        ))
                      )}
                    </select>
                  </div>

                  <div className="flex items-center gap-2 pb-2">
                    <input
                      type="checkbox"
                      id="isArchivedCheckForm"
                      checked={isArchived}
                      onChange={(e) => setIsArchived(e.target.checked)}
                      className="w-4 h-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 cursor-pointer"
                    />
                    <label htmlFor="isArchivedCheckForm" className="text-xs font-black text-slate-800 cursor-pointer select-none">
                      Archive this lead
                    </label>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-200 flex items-center justify-end gap-3 shrink-0">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsModalOpen(false)}
                  disabled={createLeadMutation.isPending || updateLeadMutation.isPending}
                  className="border-slate-300 text-black font-bold hover:bg-slate-100 text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createLeadMutation.isPending || updateLeadMutation.isPending}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold shadow-sm text-xs px-5 cursor-pointer"
                >
                  {createLeadMutation.isPending || updateLeadMutation.isPending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                      {isEditMode ? 'Saving Changes...' : 'Creating Lead...'}
                    </>
                  ) : (
                    isEditMode ? 'Save Changes' : 'Create Lead'
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION MODAL DIALOG */}
      {isDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-md bg-white rounded-2xl border border-slate-300 shadow-2xl overflow-hidden text-black">
            <div className="p-5 border-b border-slate-200 bg-rose-50 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-rose-600 flex items-center justify-center text-white shrink-0">
                  <Trash2 className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-black text-rose-950">Delete Sales Lead</h3>
                  <p className="text-xs font-bold text-rose-700">Confirm permanent lead removal</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsDeleteModalOpen(false)}
                disabled={deleteLeadMutation.isPending}
                className="p-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-200 transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <p className="text-xs font-bold text-slate-700 leading-relaxed">
                Are you sure you want to delete sales lead <span className="font-black text-slate-950">"{lead.contact_name}"</span> ({lead.company})?
              </p>
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 text-[11px] font-bold">
                ⚠️ Warning: This action cannot be undone and will permanently remove this lead from the database.
              </div>

              <div className="pt-2 flex items-center justify-end gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsDeleteModalOpen(false)}
                  disabled={deleteLeadMutation.isPending}
                  className="border-slate-300 text-black font-bold hover:bg-slate-100 text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  onClick={handleConfirmDelete}
                  disabled={deleteLeadMutation.isPending}
                  className="bg-rose-600 hover:bg-rose-700 text-white font-bold shadow-sm text-xs px-5 cursor-pointer"
                >
                  {deleteLeadMutation.isPending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                      Deleting Lead...
                    </>
                  ) : (
                    'Delete Lead'
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
