'use client';

import { getErrorMessage } from '@/lib/utils';
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
  Upload,
  Flame,
  Snowflake,
  AlertTriangle,
} from 'lucide-react';
import { Button, Card, Label, Input, Alert, AlertDescription } from '@/components/ui';
import { ModalShell } from '@/components/common/modal-shell';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
  type LeadIntelligenceResult,
} from '@/lib/api/leads';
import { useCurrentOrganizationQuery } from '@/lib/api/organizations';
import { useCompaniesQuery } from '@/lib/api/companies';
import { useUsersQuery } from '@/lib/api/users';
import { useQueryClient } from '@tanstack/react-query';
import { BASE_URL } from '@/lib/api/client';
import { formatDate, formatDateTime } from '@/lib/formatters/date';
import { CustomFieldValues } from '@/components/common/custom-field-values';
import { useEntityCustomFieldsQuery } from '@/lib/api/custom-fields';

const UNASSIGNED_VALUE = '__unassigned__';

export default function LeadDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const leadId = (params?.id as string) || '';

  // Active Tab State
  const [activeTab, setActiveTab] = useState<'overview' | 'notes' | 'tasks' | 'emails' | 'calls' | 'documents' | 'actions'>('overview');

  // Queries
  const { data: lead, isLoading, isError, error, refetch } = useLeadQuery(leadId);
  const { data: customFields = [] } = useEntityCustomFieldsQuery('Lead');
  const { data: currentOrganization, isLoading: isOrgsLoading } = useCurrentOrganizationQuery();
  const organizations = useMemo(
    () => (currentOrganization ? [currentOrganization] : []),
    [currentOrganization],
  );
  const { data: companies = [] } = useCompaniesQuery();
  const {
    data: users = [],
    isLoading: isUsersLoading,
    isFetching: isUsersFetching,
    isError: isUsersError,
    refetch: refetchUsers,
  } = useUsersQuery(1, 100);

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
  const [leadIntelligence, setLeadIntelligence] = useState<LeadIntelligenceResult | null>(null);
  const [isConverting, setIsConverting] = useState(false);
  const [assignmentSelection, setAssignmentSelection] = useState({ leadId: '', value: UNASSIGNED_VALUE });
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
  const [assignedTo, setAssignedTo] = useState<string>('');
  const [isArchived, setIsArchived] = useState<boolean>(false);

  const orgName = useMemo(() => {
    if (!lead?.organization_id) return 'Enterprise Organization';
    const found = organizations.find((o) => o.id === lead.organization_id);
    if (found) return found.name;
    if (lead.organization_id.includes('-') && lead.organization_id.length > 20) {
      return organizations.length > 0 ? organizations[0].name : 'Enterprise Organization';
    }
    return lead.organization_id;
  }, [lead, organizations]);

  const leadTimeZone = organizations.find(
    (organization) => organization.id === lead?.organization_id,
  )?.timezone || 'UTC';
  const savedAssignedUser = lead?.assigned_to
    ? users.find(
        (user) => user.id === lead.assigned_to || user.email === lead.assigned_to || user.name === lead.assigned_to,
      )
    : undefined;
  const savedAssigneeValue = savedAssignedUser?.id || lead?.assigned_to || UNASSIGNED_VALUE;

  const selectedAssignUser = assignmentSelection.leadId === leadId
    ? assignmentSelection.value
    : savedAssigneeValue;
  const isAssignmentChanged = selectedAssignUser !== savedAssigneeValue;
  const isCurrentAssigneeMissing = savedAssigneeValue !== UNASSIGNED_VALUE
    && !users.some((user) => user.id === savedAssigneeValue);
  const isAssignmentUnavailable = isUsersLoading
    || isUsersError
    || (users.length === 0 && savedAssigneeValue === UNASSIGNED_VALUE);

  const assignedUserName = useMemo(() => {
    if (!lead?.assigned_to) return 'Unassigned';
    const found = users.find(
      (u) => u.id === lead.assigned_to || u.email === lead.assigned_to || u.name === lead.assigned_to
    );
    if (found) return found.name || found.email;
    if (lead.assigned_to.includes('-') && lead.assigned_to.length > 20) {
      const firstUser = users.find((u) => u.name) || users[0];
      return firstUser ? (firstUser.name || firstUser.email) : 'Selva Admin';
    }
    return lead.assigned_to;
  }, [lead, users]);

  const formatFileSize = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
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
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to save lead.'));
    }
  };

  const handleConfirmDelete = async () => {
    if (!lead) return;
    try {
      await deleteLeadMutation.mutateAsync(lead.id);
      setIsDeleteModalOpen(false);
      router.push('/leads');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete lead.'));
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
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to add note.'));
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
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to create task.'));
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
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to send email.'));
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
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to log call.'));
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
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to upload document.'));
    } finally {
      setIsUploadingDoc(false);
    }
  };

  const handleRecalculateScore = async () => {
    try {
      setIsRecalculatingScore(true);
      const result = await recalculateLeadScoreApi(leadId);
      setLeadIntelligence(result);
      await refetch();
      setSuccessMessage('AI lead intelligence updated.');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch {
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
    } catch {
      setErrorMessage('Failed to convert lead.');
    } finally {
      setIsConverting(false);
    }
  };

  const handleAssignLead = async () => {
    if (!lead || !isAssignmentChanged) return;
    const isUnassigning = selectedAssignUser === UNASSIGNED_VALUE;
    try {
      setIsAssigning(true);
      if (isUnassigning) {
        await updateLeadMutation.mutateAsync({ id: leadId, payload: { assigned_to: null } });
      } else {
        await assignLeadApi(leadId, selectedAssignUser);
      }
      await refetch();
      setSuccessMessage(isUnassigning ? 'Lead unassigned successfully!' : 'Lead assigned successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch {
      setErrorMessage(isUnassigning ? 'Failed to unassign lead.' : 'Failed to assign lead.');
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
    } catch {
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

  const leadScore = typeof lead.score === 'number' ? lead.score : null;

  return (
    <div className="w-full space-y-6 text-[#374151] pb-16 px-1 sm:px-2">
      {/* Breadcrumb Navigation */}
      <nav className="flex items-center gap-2 text-caption font-medium text-[#6B7280]">
        <Link href="/leads" className="hover:text-[#2563EB] transition flex items-center gap-1">
          <ArrowLeft className="w-3.5 h-3.5" /> Leads
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-[#9CA3AF]" />
        <span className="text-[#111827] font-semibold truncate max-w-[200px] sm:max-w-none">
          {lead.contact_name}
        </span>
      </nav>

      {/* Success Banner */}
      {successMessage && (
        <Alert variant="default" className="bg-[#16A34A]/10 border-[#16A34A]/20 text-[#16A34A] font-medium animate-in fade-in-50">
          <CheckCircle2 className="h-4 w-4 text-[#16A34A] mr-2" />
          <AlertDescription className="text-[#16A34A] font-medium">
            {successMessage}
          </AlertDescription>
        </Alert>
      )}

      {/* Header Banner */}
      <div className="bg-white border border-[#E5E7EB] shadow-saas-sm rounded-card p-5 sm:p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-5">
        <div className="flex items-start sm:items-center gap-4">
          <div className="w-14 h-14 rounded-btn bg-[#2563EB] flex items-center justify-center text-white font-semibold text-xl shadow-saas-sm shrink-0">
            {lead.contact_name ? lead.contact_name.charAt(0).toUpperCase() : 'L'}
          </div>
          <div className="space-y-1">
            <div className="flex items-center flex-wrap gap-2.5">
              <h1 className="text-page-title text-[#111827]">
                {lead.contact_name}
              </h1>
              <span className="px-2.5 py-0.5 rounded-full bg-[#2563EB]/10 border border-[#2563EB]/20 text-[#2563EB] text-badge font-semibold">
                {lead.status}
              </span>
            </div>
            <p className="text-body font-medium text-[#6B7280] flex items-center gap-2 flex-wrap">
              <span>{lead.title}</span>
              <span className="text-[#9CA3AF]" aria-hidden="true">•</span>
              <span className="text-[#2563EB] font-semibold">{lead.company}</span>
            </p>
          </div>
        </div>

        {/* Header Actions */}
        <div className="flex items-center gap-2.5 shrink-0 flex-wrap">
          <Button
            type="button"
            variant="outline"
            size="default"
            onClick={handleOpenEditModal}
            className="text-button font-medium cursor-pointer"
          >
            <Pencil className="w-4 h-4 mr-2" /> Edit Lead
          </Button>
          <Button
            type="button"
            variant="outline"
            size="default"
            onClick={() => setIsDeleteModalOpen(true)}
            className="border-rose-200 text-rose-700 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-800 text-button font-medium cursor-pointer"
          >
            <Trash2 className="w-4 h-4 mr-2" /> Delete Lead
          </Button>
        </div>
      </div>

      {/* Enterprise Tabbed Interface Header */}
      <div className="sticky top-0 z-20 -mx-1 border-b border-[#E5E7EB] bg-slate-50/95 px-1 pt-2 backdrop-blur-sm sm:-mx-2 sm:px-2 overflow-x-auto scrollbar-none">
        <nav className="flex space-x-2 min-w-max pb-1">
          {([
            { id: 'overview', label: 'Overview & Details', icon: Briefcase },
            { id: 'notes', label: `Notes (${notes.length})`, icon: FileText },
            { id: 'tasks', label: `Tasks (${tasks.length})`, icon: CheckSquare },
            { id: 'emails', label: `Emails (${emails.length})`, icon: Send },
            { id: 'calls', label: `Calls (${calls.length})`, icon: PhoneCall },
            { id: 'documents', label: `Documents (${documents.length})`, icon: Paperclip },
            { id: 'actions', label: 'Actions & Convert', icon: Zap },
          ] as const).map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 text-button font-medium rounded-btn transition cursor-pointer border ${isActive
                    ? 'bg-[#2563EB] text-white border-[#2563EB] shadow-saas-sm font-semibold'
                    : 'bg-white text-[#374151] hover:bg-[#F3F4F6] border-[#E5E7EB]'
                  }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-[#6B7280]'}`} />
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
            <Card className="p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-card space-y-6">
              <div className="border-b border-[#E5E7EB] pb-4">
                <h2 className="text-subheading font-semibold text-[#111827] flex items-center gap-2">
                  <Briefcase className="w-4 h-4 text-[#2563EB]" />
                  Lead Overview & Contact Info
                </h2>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div className="space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">Contact Name</span>
                  <p className="text-body font-medium text-[#111827]">{lead.contact_name}</p>
                </div>

                <div className="space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">Opportunity Title</span>
                  <p className="text-body font-medium text-[#111827]">{lead.title}</p>
                </div>

                <div className="space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">Email Address</span>
                  <p className="text-body font-medium text-[#2563EB] flex items-center gap-2">
                    <Mail className="w-4 h-4 text-[#9CA3AF] shrink-0" />
                    <a href={`mailto:${lead.email}`} className="hover:underline truncate">{lead.email}</a>
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">Phone Number</span>
                  <p className="text-body font-medium text-[#111827] flex items-center gap-2">
                    <Phone className="w-4 h-4 text-[#9CA3AF] shrink-0" />
                    {lead.phone ? <a href={`tel:${lead.phone}`} className="hover:underline">{lead.phone}</a> : <span className="text-[#9CA3AF] italic">Not provided</span>}
                  </p>
                </div>
              </div>
            </Card>

            <CustomFieldValues fields={customFields} values={lead.custom_fields ?? {}} />

            <Card className="p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-card space-y-6">
              <div className="border-b border-[#E5E7EB] pb-4">
                <h2 className="text-subheading font-semibold text-[#111827] flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-[#2563EB]" />
                  Company & Industry Details
                </h2>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div className="space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">Company Name</span>
                  <p className="text-body font-medium text-[#111827]">{lead.company}</p>
                </div>

                <div className="space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">Industry</span>
                  <p className="text-body font-medium text-[#111827]">{lead.industry || <span className="text-[#9CA3AF] italic">N/A</span>}</p>
                </div>

                <div className="space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">Company Size</span>
                  <p className="text-body font-medium text-[#111827]">{lead.company_size || <span className="text-[#9CA3AF] italic">N/A</span>}</p>
                </div>

                <div className="space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">Website</span>
                  <p className="text-body font-medium text-[#2563EB] flex items-center gap-2">
                    <Globe className="w-4 h-4 text-[#9CA3AF] shrink-0" />
                    {lead.website ? (
                      <a href={lead.website.startsWith('http') ? lead.website : `https://${lead.website}`} target="_blank" rel="noreferrer" className="hover:underline truncate">
                        {lead.website}
                      </a>
                    ) : (
                      <span className="text-[#9CA3AF] italic">N/A</span>
                    )}
                  </p>
                </div>
              </div>
            </Card>

            <Card className="p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-card space-y-6">
              <div className="border-b border-[#E5E7EB] pb-4">
                <h2 className="text-subheading font-semibold text-[#111827] flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-[#2563EB]" />
                  Address & Location
                </h2>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div className="sm:col-span-2 space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">Street Address</span>
                  <p className="text-body font-medium text-[#111827]">{lead.address || <span className="text-[#9CA3AF] italic">Not provided</span>}</p>
                </div>

                <div className="space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">City</span>
                  <p className="text-body font-medium text-[#111827]">{lead.city || <span className="text-[#9CA3AF] italic">N/A</span>}</p>
                </div>

                <div className="space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">State</span>
                  <p className="text-body font-medium text-[#111827]">{lead.state || <span className="text-[#9CA3AF] italic">N/A</span>}</p>
                </div>

                <div className="space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">Country</span>
                  <p className="text-body font-medium text-[#111827]">{lead.country || <span className="text-[#9CA3AF] italic">N/A</span>}</p>
                </div>

                <div className="space-y-1">
                  <span className="text-caption font-medium uppercase text-[#6B7280] tracking-wider">Postal Code</span>
                  <p className="text-body font-medium text-[#111827]">{lead.postal_code || <span className="text-[#9CA3AF] italic">N/A</span>}</p>
                </div>
              </div>
            </Card>
          </div>
          <div className="space-y-6">
            <Card className="p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-card space-y-5">
              <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
                <span className="text-subheading font-semibold text-[#111827] flex items-center gap-1.5">
                  <Activity className="w-4 h-4 text-[#2563EB]" /> Qualification Score
                </span>
                {leadScore === null ? (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-[#F3F4F6] text-[#374151] border border-[#E5E7EB] text-badge font-semibold">
                    Not scored
                  </span>
                ) : leadScore >= 70 ? (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[#16A34A]/10 text-[#16A34A] border border-[#16A34A]/20 text-badge font-semibold">
                    <Flame className="size-3" aria-hidden="true" /> High Intent
                  </span>
                ) : leadScore >= 40 ? (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[#F59E0B]/10 text-[#D97706] border border-[#F59E0B]/20 text-badge font-semibold">
                    <Zap className="size-3" aria-hidden="true" /> Warm Lead
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[#F3F4F6] text-[#374151] border border-[#E5E7EB] text-badge font-semibold">
                    <Snowflake className="size-3" aria-hidden="true" /> Cold Lead
                  </span>
                )}
              </div>

              <div className="flex items-baseline justify-between">
                <div>
                  <div className="text-page-title text-[#111827]">
                    {leadScore ?? '—'}
                    <span className="text-body font-medium text-[#6B7280] ml-1">/ 100</span>
                  </div>
                  <p className="text-caption font-medium text-[#6B7280] mt-0.5">Engagement & Conversion Potential</p>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-body font-medium text-[#374151]">
                  <span>Engagement Health</span>
                  <span className="font-semibold text-[#111827]">
                    {leadScore === null ? 'Not scored' : `${leadScore}%`}
                  </span>
                </div>
                <div className="w-full h-2.5 rounded-full bg-[#F3F4F6] overflow-hidden border border-[#E5E7EB]">
                  <div
                    className="h-full bg-[#2563EB] rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, Math.max(0, leadScore ?? 0))}%` }}
                  />
                </div>
              </div>

              <div className="pt-3 grid grid-cols-2 gap-3 border-t border-[#E5E7EB] text-caption">
                <div className="space-y-1">
                  <span className="block text-caption font-medium uppercase text-[#6B7280]">Current Stage</span>
                  <span className="inline-block px-2.5 py-0.5 rounded-btn bg-[#2563EB]/10 border border-[#2563EB]/20 text-[#2563EB] text-badge font-semibold">
                    {lead.status}
                  </span>
                </div>
                <div className="space-y-1">
                  <span className="block text-caption font-medium uppercase text-[#6B7280]">Lead Source</span>
                  <span className="inline-block px-2.5 py-0.5 rounded-btn bg-[#F3F4F6] border border-[#E5E7EB] text-[#374151] text-badge font-semibold">
                    {lead.source}
                  </span>
                </div>
              </div>
            </Card>

            <Card className="p-6 bg-white border border-[#E5E7EB] shadow-saas-sm rounded-card space-y-5">
              <h2 className="text-subheading font-semibold text-[#111827] border-b border-[#E5E7EB] pb-3 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-[#2563EB]" /> Account & Assignment
              </h2>

              <div className="space-y-4 text-body font-medium text-[#374151]">
                <div className="flex items-center justify-between">
                  <span className="text-[#6B7280] font-medium flex items-center gap-1.5">
                    <Building className="w-3.5 h-3.5 text-[#9CA3AF]" /> Organization
                  </span>
                  <span className="text-[#111827] font-semibold text-right max-w-[160px] truncate">{orgName}</span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-[#6B7280] font-medium flex items-center gap-1.5">
                    <UserCheck className="w-3.5 h-3.5 text-[#9CA3AF]" /> Assigned To
                  </span>
                  <span className="text-[#2563EB] font-semibold">{assignedUserName}</span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-[#6B7280] font-medium flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-[#9CA3AF]" /> Created Date
                  </span>
                  <span className="text-[#111827] font-medium">{formatDate(lead.created_at, { timeZone: leadTimeZone })}</span>
                </div>

                <div className="flex items-center justify-between border-t border-[#E5E7EB] pt-3">
                  <span className="text-[#6B7280] font-medium">Lead Record State</span>
                  <span className={lead.is_archived ? 'text-[#F59E0B] font-semibold' : 'text-[#16A34A] font-semibold'}>
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
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-4">
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
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Add Note
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
              <p className="text-[11px] text-slate-400">Use Add Note above to attach a note.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full min-w-[560px] text-left border-collapse text-xs">
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
                      <td className="py-3.5 px-4 font-bold text-slate-600">{formatDateTime(n.created_at, { timeZone: leadTimeZone })}</td>
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
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-4">
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
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Create Task
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
              <p className="text-[11px] text-slate-400">Use Create Task above to assign a new task.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full min-w-[560px] text-left border-collapse text-xs">
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
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-black ${t.priority === 'High' ? 'bg-rose-50 text-rose-700 border border-rose-200' :
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
                      <td className="py-3.5 px-4 font-bold text-slate-600">{formatDate(t.due_date)}</td>
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
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-4">
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
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Send Email
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
              <p className="text-[11px] text-slate-400">Use Send Email above to send an email.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full min-w-[560px] text-left border-collapse text-xs">
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
                      <td className="py-3.5 px-4 font-bold text-slate-600">{formatDateTime(e.sent_at, { timeZone: leadTimeZone })}</td>
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
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-4">
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
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Log Call
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
              <p className="text-[11px] text-slate-400">Use Log Call above to record a phone conversation.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full min-w-[560px] text-left border-collapse text-xs">
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
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-black ${c.call_type === 'Outbound' ? 'bg-indigo-50 text-indigo-700 border border-indigo-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          }`}>
                          {c.call_type} Call
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-black text-slate-900">{Math.floor(c.duration_seconds / 60)}m {c.duration_seconds % 60}s</td>
                      <td className="py-3.5 px-4 font-bold text-slate-700">{c.notes || 'N/A'}</td>
                      <td className="py-3.5 px-4 font-bold text-slate-600">{formatDateTime(c.timestamp, { timeZone: leadTimeZone })}</td>
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
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-4">
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
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Upload Document
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
              <p className="text-[11px] text-slate-400">Use Upload Document above to attach a file.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full min-w-[560px] text-left border-collapse text-xs">
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
                      <td className="py-3.5 px-4 font-bold text-slate-600">{formatDateTime(d.uploaded_at, { timeZone: leadTimeZone })}</td>
                      <td className="py-3.5 px-4 text-right">
                        {d.download_url && (
                          <a
                            href={
                              d.download_url.startsWith('http') && !d.download_url.includes('.internal')
                                ? d.download_url
                                : `${BASE_URL.replace(/\/$/, '')}/leads/${leadId}/documents/${d.id}/download`
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
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-black text-slate-950 flex items-center gap-2">
                  <Award className="w-4 h-4 text-indigo-600" /> Recalculate AI Qualification Score
                </h3>
                <p className="text-xs font-bold text-slate-600">Re-evaluates lead metrics and updates engagement score</p>
              </div>
              <PermissionGate permission={PERMISSIONS.LEADS.UPDATE}>
                <PermissionGate permission={PERMISSIONS.AI.GENERATE}>
                  <Button type="button" onClick={handleRecalculateScore} disabled={isRecalculatingScore} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-4 cursor-pointer">
                    {isRecalculatingScore ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
                    Recalculate AI Score
                  </Button>
                </PermissionGate>
              </PermissionGate>
            </div>
            {leadIntelligence && (
              <div className="grid gap-3 text-xs sm:grid-cols-3" aria-live="polite">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <span className="text-slate-500">Conversion probability</span>
                  <p className="mt-1 font-bold text-slate-900">{leadIntelligence.conversion_probability}%</p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <span className="text-slate-500">Qualification</span>
                  <p className="mt-1 font-bold text-slate-900">{leadIntelligence.qualification}</p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <span className="text-slate-500">Confidence</span>
                  <p className="mt-1 font-bold text-slate-900">{Math.round(leadIntelligence.confidence * 100)}%</p>
                </div>
                {leadIntelligence.reasons.length > 0 && (
                  <ul className="list-disc space-y-1 pl-5 text-slate-700 sm:col-span-3">
                    {leadIntelligence.reasons.map((reason) => <li key={reason}>{reason}</li>)}
                  </ul>
                )}
              </div>
            )}
          </Card>

          <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-3">
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
              <Select
                value={selectedAssignUser}
                onValueChange={(value) => setAssignmentSelection({ leadId, value })}
                disabled={isAssignmentUnavailable}
              >
                <SelectTrigger className="w-full border-slate-300 bg-white text-xs font-bold text-slate-900 sm:w-72" aria-label="Select sales representative">
                  <SelectValue placeholder={isUsersLoading ? 'Loading sales representatives...' : 'Select sales representative'} />
                </SelectTrigger>
                <SelectContent position="popper" align="start" className="w-[var(--radix-select-trigger-width)]">
                  <SelectItem value={UNASSIGNED_VALUE} className="text-xs font-semibold">
                    Unassigned
                  </SelectItem>
                  {isCurrentAssigneeMissing && (
                    <SelectItem value={savedAssigneeValue} className="text-xs font-semibold">
                      {assignedUserName} (Current)
                    </SelectItem>
                  )}
                  {users.map((u) => (
                    <SelectItem key={u.id} value={u.id} className="text-xs font-semibold">
                      {u.name} ({u.role})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button type="button" onClick={handleAssignLead} disabled={isAssigning || isAssignmentUnavailable || !isAssignmentChanged} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-4 cursor-pointer">
                {isAssigning ? (
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : selectedAssignUser === UNASSIGNED_VALUE ? (
                  'Unassign Lead'
                ) : (
                  'Assign Lead'
                )}
              </Button>
            </div>
            {isUsersLoading ? (
              <p role="status" className="text-xs font-semibold text-slate-500">Loading sales representatives...</p>
            ) : isUsersError ? (
              <div role="alert" className="flex flex-col gap-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs font-semibold text-rose-800 sm:flex-row sm:items-center sm:justify-between">
                <span>Sales representatives could not be loaded. Try again to update the assignment.</span>
                <Button type="button" variant="outline" size="sm" onClick={() => void refetchUsers()} disabled={isUsersFetching} className="shrink-0 border-rose-200 bg-white text-rose-700 hover:bg-rose-100 hover:text-rose-800">
                  {isUsersFetching && <Loader2 className="mr-1.5 size-3.5 animate-spin" />}
                  Retry
                </Button>
              </div>
            ) : !isUsersLoading && users.length === 0 && savedAssigneeValue === UNASSIGNED_VALUE ? (
              <p className="text-xs font-semibold text-slate-500">No sales representatives are available for assignment.</p>
            ) : null}
          </Card>

          <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-3">
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
        <ModalShell
          isOpen={isNoteModalOpen}
          onClose={() => setIsNoteModalOpen(false)}
          size="lg"
          title={
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                <FileText className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-base font-black text-black">Add Lead Note</h3>
                <p className="text-xs font-bold text-slate-600">Attach a note for {lead.contact_name}</p>
              </div>
            </div>
          }
        >
          <form onSubmit={handleAddNote} className="space-y-4">
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
            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2 border-t border-slate-100">
              <Button type="button" variant="outline" onClick={() => setIsNoteModalOpen(false)} className="border-slate-300 text-black font-bold text-xs">
                Cancel
              </Button>
              <Button type="submit" disabled={isAddingNote} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-5 cursor-pointer">
                {isAddingNote ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : 'Save Note'}
              </Button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* MODAL 2: CREATE TASK MODAL */}
      {isTaskModalOpen && (
        <ModalShell
          isOpen={isTaskModalOpen}
          onClose={() => setIsTaskModalOpen(false)}
          size="lg"
          title={
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                <CheckSquare className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-base font-black text-black">Create Lead Task</h3>
                <p className="text-xs font-bold text-slate-600">Assign a task for {lead.contact_name}</p>
              </div>
            </div>
          }
        >
          <form onSubmit={handleCreateTask} className="space-y-4">
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
            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2 border-t border-slate-100">
              <Button type="button" variant="outline" onClick={() => setIsTaskModalOpen(false)} className="border-slate-300 text-black font-bold text-xs">
                Cancel
              </Button>
              <Button type="submit" disabled={isCreatingTask} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-5 cursor-pointer">
                {isCreatingTask ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : 'Create Task'}
              </Button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* MODAL 3: SEND EMAIL MODAL */}
      {isEmailModalOpen && (
        <ModalShell
          isOpen={isEmailModalOpen}
          onClose={() => setIsEmailModalOpen(false)}
          size="lg"
          title={
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                <Send className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-base font-black text-black">Send Email</h3>
                <p className="text-xs font-bold text-slate-600">Send email to {lead.contact_name}</p>
              </div>
            </div>
          }
        >
          <form onSubmit={handleSendEmail} className="space-y-4">
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
            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2 border-t border-slate-100">
              <Button type="button" variant="outline" onClick={() => setIsEmailModalOpen(false)} className="border-slate-300 text-black font-bold text-xs">
                Cancel
              </Button>
              <Button type="submit" disabled={isSendingEmail} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-5 cursor-pointer">
                {isSendingEmail ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : 'Send Email'}
              </Button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* MODAL 4: LOG CALL MODAL */}
      {isCallModalOpen && (
        <ModalShell
          isOpen={isCallModalOpen}
          onClose={() => setIsCallModalOpen(false)}
          size="lg"
          title={
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                <PhoneCall className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-base font-black text-black">Log Phone Call</h3>
                <p className="text-xs font-bold text-slate-600">Record call with {lead.contact_name}</p>
              </div>
            </div>
          }
        >
          <form onSubmit={handleLogCall} className="space-y-4">
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
            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2 border-t border-slate-100">
              <Button type="button" variant="outline" onClick={() => setIsCallModalOpen(false)} className="border-slate-300 text-black font-bold text-xs">
                Cancel
              </Button>
              <Button type="submit" disabled={isLoggingCall} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-5 cursor-pointer">
                {isLoggingCall ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : 'Log Call'}
              </Button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* MODAL 5: UPLOAD DOCUMENT MODAL */}
      {isDocModalOpen && (
        <ModalShell
          isOpen={isDocModalOpen}
          onClose={() => setIsDocModalOpen(false)}
          size="lg"
          title={
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                <Upload className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-base font-black text-black">Upload Lead Document</h3>
                <p className="text-xs font-bold text-slate-600">Attach file to MinIO S3 for {lead.contact_name}</p>
              </div>
            </div>
          }
        >
          <form onSubmit={handleUploadDocument} className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-black text-black">Choose File *</Label>
              <input
                type="file"
                required
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
              />
            </div>
            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2 border-t border-slate-100">
              <Button type="button" variant="outline" onClick={() => setIsDocModalOpen(false)} className="border-slate-300 text-black font-bold text-xs">
                Cancel
              </Button>
              <Button type="submit" disabled={isUploadingDoc || !selectedFile} className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-5 cursor-pointer">
                {isUploadingDoc ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : 'Upload File'}
              </Button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* CREATE & EDIT LEAD MODAL DIALOG */}
      {isModalOpen && (
        <ModalShell
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          size="3xl"
          title={
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
          }
        >
          {errorMessage && (
            <div className="pb-4">
              <Alert variant="destructive" className="bg-rose-50 border-rose-300 text-rose-950 font-bold">
                <AlertCircle className="h-4 w-4 text-rose-600 mr-2" />
                <AlertDescription className="text-rose-900 font-bold text-xs">{errorMessage}</AlertDescription>
              </Alert>
            </div>
          )}

          <form onSubmit={handleSubmitForm} className="space-y-6">
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

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1 items-end">
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

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-4 border-t border-slate-200">
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
        </ModalShell>
      )}

      {/* DELETE CONFIRMATION MODAL DIALOG */}
      {isDeleteModalOpen && (
        <ModalShell
          isOpen={isDeleteModalOpen}
          onClose={() => setIsDeleteModalOpen(false)}
          size="md"
          title={
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-rose-600 flex items-center justify-center text-white shrink-0">
                <Trash2 className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-base font-black text-rose-950">Delete Sales Lead</h3>
                <p className="text-xs font-bold text-rose-700">Confirm permanent lead removal</p>
              </div>
            </div>
          }
        >
          <div className="space-y-4">
            <p className="text-xs font-bold text-slate-700 leading-relaxed">
              Are you sure you want to delete sales lead <span className="font-black text-slate-950">&quot;{lead.contact_name}&quot;</span> ({lead.company})?
            </p>
            <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 text-[11px] font-bold">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span>Warning: This action cannot be undone and will permanently remove this lead from the database.</span>
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
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
        </ModalShell>
      )}
    </div>
  );
}
