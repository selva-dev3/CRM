'use client';

import { ResponsiveSelect } from '@/components/common/responsive-select';
import { DateTimePicker } from '@/components/common/date-picker';
import { Textarea } from '@/components/ui/textarea';

import { getErrorMessage } from '@/lib/utils';
import React, { useMemo, useRef, useState } from 'react';
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
  History,
} from 'lucide-react';
import { Button, Card, Label, Input, Alert, AlertDescription } from '@/components/ui';
import { ModalShell } from '@/components/common/modal-shell';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { EmailBodyPreview } from '@/components/common/email-body-preview';
import { PageTabs } from '@/components/common/page-tabs';
import { PermissionGate } from '@/components/common/permission-gate';
import { LeadCallLogSection } from '@/components/features/leads/lead-call-log-section';
import { LeadFormDialog } from '@/components/features/leads/lead-form-dialog';
import { useHasPermission } from '@/hooks/use-has-permission';
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
  useLeadTimelineQuery,
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
  uploadLeadDocumentApi,
  recalculateLeadScoreApi,
  convertLeadApi,
  qualifyLeadApi,
  disqualifyLeadApi,
  reopenLeadApi,
  assignLeadApi,
  archiveLeadApi,
  unarchiveLeadApi,
  type LeadEmailItem,
  type LeadNoteItem,
  type LeadTaskItem,
  type LeadDocumentItem,
  type LeadIntelligenceResult,
} from '@/lib/api/leads';
import { useCurrentOrganizationQuery } from '@/lib/api/organizations';
import { useUsersQuery } from '@/lib/api/users';
import { useQueryClient } from '@tanstack/react-query';
import { BASE_URL } from '@/lib/api/client';
import { formatDate, formatDateTime } from '@/lib/formatters/date';
import { CustomFieldValues } from '@/components/common/custom-field-values';
import {
  useEntityCustomFieldsQuery,
} from '@/lib/api/custom-fields';

const UNASSIGNED_VALUE = '__unassigned__';
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function isValidEmail(value: string | null | undefined): value is string {
  return typeof value === 'string' && EMAIL_PATTERN.test(value.trim());
}

function createIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `lead-email-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function formatFileSize(bytes: number): string {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const unitIndex = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${parseFloat((bytes / Math.pow(1024, unitIndex)).toFixed(1))} ${units[unitIndex]}`;
}

export default function LeadDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { hasPermission } = useHasPermission();
  const leadId = (params?.id as string) || '';
  const canReadCalls = hasPermission(PERMISSIONS.CALLS.READ);
  const relationPageSize = 15;
  const [timelinePage, setTimelinePage] = useState(1);
  const [notesPage, setNotesPage] = useState(1);
  const [tasksPage, setTasksPage] = useState(1);
  const [emailsPage, setEmailsPage] = useState(1);
  const [callsPage, setCallsPage] = useState(1);
  const [documentsPage, setDocumentsPage] = useState(1);

  // Active Tab State
  const [activeTab, setActiveTab] = useState<'overview' | 'timeline' | 'notes' | 'tasks' | 'emails' | 'calls' | 'documents' | 'actions'>('overview');

  // Queries
  const { data: lead, isLoading, isError, error, refetch } = useLeadQuery(leadId);
  const { data: timelinePageData, isLoading: isTimelineLoading, refetch: refetchTimeline } = useLeadTimelineQuery(leadId, timelinePage, relationPageSize);
  const { data: customFields = [] } = useEntityCustomFieldsQuery('Lead');
  const { data: currentOrganization } = useCurrentOrganizationQuery();
  const organizations = useMemo(
    () => (currentOrganization ? [currentOrganization] : []),
    [currentOrganization],
  );
  const {
    data: users = [],
    isLoading: isUsersLoading,
    isFetching: isUsersFetching,
    isError: isUsersError,
    refetch: refetchUsers,
  } = useUsersQuery(1, 100);

  // Sub-resource Queries
  const { data: notesPageData, refetch: refetchNotes, isLoading: isNotesLoading } = useLeadNotesQuery(leadId, notesPage, relationPageSize);
  const { data: tasksPageData, refetch: refetchTasks, isLoading: isTasksLoading } = useLeadTasksQuery(leadId, tasksPage, relationPageSize);
  const { data: emailsPageData, refetch: refetchEmails, isLoading: isEmailsLoading } = useLeadEmailsQuery(leadId, emailsPage, relationPageSize);
  const {
    data: callsPageData,
    isLoading: isCallsLoading,
    isError: isCallsError,
    error: callsError,
    refetch: refetchCalls,
  } = useLeadCallsQuery(leadId, canReadCalls, callsPage, relationPageSize);
  const { data: documentsPageData, refetch: refetchDocuments, isLoading: isDocsLoading } = useLeadDocumentsQuery(leadId, documentsPage, relationPageSize);
  const timeline = timelinePageData?.items ?? [];
  const notes = notesPageData?.items ?? [];
  const tasks = tasksPageData?.items ?? [];
  const emails = emailsPageData?.items ?? [];
  const calls = callsPageData?.items ?? [];
  const documents = documentsPageData?.items ?? [];

  // Lead Mutations
  const updateLeadMutation = useUpdateLeadMutation();
  const deleteLeadMutation = useDeleteLeadMutation();

  // Banners & Modals State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Sub-resource Modal Trigger States
  const [isNoteModalOpen, setIsNoteModalOpen] = useState(false);
  const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
  const [isEmailModalOpen, setIsEmailModalOpen] = useState(false);
  const [isDocModalOpen, setIsDocModalOpen] = useState(false);

  // Form Inputs
  const [newNote, setNewNote] = useState('');
  const [isAddingNote, setIsAddingNote] = useState(false);

  const [taskTitle, setTaskTitle] = useState('');
  const [taskDesc, setTaskDesc] = useState('');
  const [taskPriority, setTaskPriority] = useState('Medium');
  const [taskDueDate, setTaskDueDate] = useState('');
  const [taskErrorMessage, setTaskErrorMessage] = useState<string | null>(null);
  const [isCreatingTask, setIsCreatingTask] = useState(false);
  const taskTitleRef = useRef<HTMLInputElement | null>(null);
  const taskDueDateRef = useRef<HTMLButtonElement | null>(null);

  const [emailTo, setEmailTo] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [emailBody, setEmailBody] = useState('');
  const [isSendingEmail, setIsSendingEmail] = useState(false);
  const emailIdempotencyKeyRef = useRef<string | null>(null);


  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploadingDoc, setIsUploadingDoc] = useState(false);

  const [isRecalculatingScore, setIsRecalculatingScore] = useState(false);
  const [leadIntelligence, setLeadIntelligence] = useState<LeadIntelligenceResult | null>(null);
  const [isConverting, setIsConverting] = useState(false);
  const [assignmentSelection, setAssignmentSelection] = useState({ leadId: '', value: UNASSIGNED_VALUE });
  const [isAssigning, setIsAssigning] = useState(false);
  const [isArchiving, setIsArchiving] = useState(false);
  const [lifecycleAction, setLifecycleAction] = useState<'qualify' | 'disqualify' | null>(null);
  const [lifecycleReason, setLifecycleReason] = useState('');
  const [isUpdatingLifecycle, setIsUpdatingLifecycle] = useState(false);

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
  const emailColumns = useMemo<readonly DataTableColumn<LeadEmailItem>[]>(() => [
    {
      id: 'subject',
      header: 'Subject',
      cell: (email) => email.subject || 'No subject',
    },
    {
      id: 'recipient',
      header: 'Recipient',
      cell: (email) => email.to.length > 0 ? email.to.join(', ') : 'N/A',
    },
    {
      id: 'sender',
      header: 'Sender',
      cell: (email) => email.from_email || 'N/A',
    },
    {
      id: 'status',
      header: 'Status',
      cell: (email) => email.status || 'N/A',
    },
    {
      id: 'sent_at',
      header: 'Sent Date',
      cell: (email) => email.sent_at
        ? formatDateTime(email.sent_at, { timeZone: leadTimeZone })
        : 'N/A',
    },
  ], [leadTimeZone]);
  const noteColumns = useMemo<readonly DataTableColumn<LeadNoteItem>[]>(() => [
    { id: 'content', header: 'Note Content', cell: (note) => <span className="font-bold text-slate-900">{note.content}</span>, className: 'max-w-md whitespace-normal' },
    { id: 'author', header: 'Author / Created By', cell: (note) => <span className="font-bold text-indigo-600">{note.created_by || 'System User'}</span> },
    { id: 'created', header: 'Created Date', cell: (note) => <span className="font-bold text-slate-600">{formatDateTime(note.created_at, { timeZone: leadTimeZone })}</span> },
  ], [leadTimeZone]);
  const taskColumns = useMemo<readonly DataTableColumn<LeadTaskItem>[]>(() => [
    {
      id: 'task',
      header: 'Task Title & Description',
      cell: (task) => (
        <div className="space-y-0.5">
          <div className="font-black text-slate-900">{task.title}</div>
          {task.description && <div className="text-[11px] font-bold text-slate-500">{task.description}</div>}
        </div>
      ),
    },
    {
      id: 'priority',
      header: 'Priority',
      cell: (task) => (
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-black ${task.priority === 'High' ? 'border border-rose-200 bg-rose-50 text-rose-700' : task.priority === 'Medium' ? 'border border-amber-200 bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-700'}`}>
          {task.priority || 'Medium'}
        </span>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      cell: (task) => <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] font-black text-indigo-700">{task.status || 'Pending'}</span>,
    },
    { id: 'due', header: 'Due Date', cell: (task) => <span className="font-bold text-slate-600">{formatDate(task.due_date)}</span> },
  ], []);
  const documentColumns = useMemo<readonly DataTableColumn<LeadDocumentItem>[]>(() => [
    {
      id: 'filename',
      header: 'Filename',
      cell: (document) => (
        <div className="flex items-center gap-2 font-black text-slate-900">
          <Paperclip className="size-3.5 shrink-0 text-indigo-600" />
          <span className="max-w-[200px] truncate">{document.filename}</span>
        </div>
      ),
    },
    { id: 'size', header: 'File Size', cell: (document) => <span className="font-bold text-slate-700">{formatFileSize(document.file_size)}</span> },
    { id: 'type', header: 'MIME Type', cell: (document) => <span className="font-bold text-slate-600">{document.mime_type || 'application/pdf'}</span> },
    { id: 'uploaded', header: 'Uploaded Date', cell: (document) => <span className="font-bold text-slate-600">{formatDateTime(document.uploaded_at, { timeZone: leadTimeZone })}</span> },
    {
      id: 'download',
      header: 'Action',
      className: 'text-right',
      cell: (document) => document.download_url ? (
        <a
          href={document.download_url.startsWith('http') && !document.download_url.includes('.internal')
            ? document.download_url
            : `${BASE_URL.replace(/\/$/, '')}/leads/${leadId}/documents/${document.id}/download`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center text-xs font-black text-indigo-600 hover:text-indigo-800 hover:underline"
        >
          <Download className="mr-1 size-3" /> Download
        </a>
      ) : '—',
    },
  ], [leadId, leadTimeZone]);
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
      return 'Unavailable user';
    }
    return lead.assigned_to;
  }, [lead, users]);

  const handleOpenEditModal = () => {
    if (!lead) return;
    setErrorMessage(null);
    setIsModalOpen(true);
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
      await refetchTimeline();
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
    if (!taskTitle.trim()) {
      setTaskErrorMessage('Task title is required.');
      taskTitleRef.current?.focus();
      return;
    }
    if (!taskDueDate) {
      setTaskErrorMessage('Follow-up due date is required.');
      taskDueDateRef.current?.focus();
      return;
    }
    setTaskErrorMessage(null);
    try {
      setIsCreatingTask(true);
      await createLeadTaskApi(leadId, {
        title: taskTitle.trim(),
        description: taskDesc.trim(),
        priority: taskPriority,
        due_date: new Date(taskDueDate).toISOString(),
      });
      setTaskTitle('');
      setTaskDesc('');
      setTaskDueDate('');
      setTaskErrorMessage(null);
      setIsTaskModalOpen(false);
      await refetchTasks();
      await Promise.all([refetch(), refetchTimeline()]);
      setSuccessMessage('Task created successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: unknown) {
      setTaskErrorMessage(getErrorMessage(err, 'Failed to create task.'));
    } finally {
      setIsCreatingTask(false);
    }
  };

  const handleSendEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    const recipient = lead?.email?.trim() ?? '';
    const subject = emailSubject.trim();
    const body = emailBody.trim();

    if (!isValidEmail(recipient)) {
      setErrorMessage('This lead does not have a valid email address.');
      return;
    }
    if (!subject) {
      setErrorMessage('Subject is required.');
      return;
    }
    if (!body) {
      setErrorMessage('Email body is required.');
      return;
    }

    try {
      setIsSendingEmail(true);
      const idempotencyKey = emailIdempotencyKeyRef.current ?? createIdempotencyKey();
      emailIdempotencyKeyRef.current = idempotencyKey;
      const queuedEmail = await sendLeadEmailApi(
        leadId,
        { to: [recipient], subject, body },
        idempotencyKey,
      );
      emailIdempotencyKeyRef.current = null;
      setEmailSubject('');
      setEmailBody('');
      setIsEmailModalOpen(false);
      setSuccessMessage(
        queuedEmail.status === 'Sent'
          ? 'Email sent successfully.'
          : 'Email queued for delivery.',
      );
      try {
        await Promise.all([refetchEmails(), refetchTimeline()]);
      } catch {
        setErrorMessage('Email queued for delivery, but the activity history could not refresh.');
      }
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to send email.'));
    } finally {
      setIsSendingEmail(false);
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
      await refetchTimeline();
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
    if (isConverting) return;
    try {
      setIsConverting(true);
      setErrorMessage(null);
      const result = await convertLeadApi(leadId, { create_deal: true, deal_title: `${lead?.contact_name} Deal` });
      await Promise.all([
        refetch(),
        refetchTimeline(),
        ...['leads', 'contacts', 'companies', 'deals'].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] })),
      ]);
      setSuccessMessage(result.deal_id
        ? 'Lead converted to Deal, Contact, and Company!'
        : 'Lead converted to Contact and Company.');
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to convert lead.');
    } finally {
      setIsConverting(false);
    }
  };

  const refreshLifecycle = async () => {
    await Promise.all([
      refetch(),
      refetchTimeline(),
      queryClient.invalidateQueries({ queryKey: ['leads'] }),
    ]);
  };

  const handleLifecycleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lifecycleAction) return;
    if (lifecycleAction === 'disqualify' && !lifecycleReason.trim()) {
      setErrorMessage('A disqualification reason is required.');
      return;
    }
    try {
      setIsUpdatingLifecycle(true);
      setErrorMessage(null);
      if (lifecycleAction === 'qualify') {
        await qualifyLeadApi(leadId, lifecycleReason.trim() || undefined);
      } else {
        await disqualifyLeadApi(leadId, lifecycleReason.trim());
      }
      await refreshLifecycle();
      setSuccessMessage(
        lifecycleAction === 'qualify' ? 'Lead qualified successfully.' : 'Lead disqualified.',
      );
      setLifecycleAction(null);
      setLifecycleReason('');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to update lead lifecycle.'));
    } finally {
      setIsUpdatingLifecycle(false);
    }
  };

  const handleReopenLead = async () => {
    try {
      setIsUpdatingLifecycle(true);
      setErrorMessage(null);
      await reopenLeadApi(leadId);
      await refreshLifecycle();
      setSuccessMessage('Lead reopened as Contacted.');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to reopen lead.'));
    } finally {
      setIsUpdatingLifecycle(false);
    }
  };

  const handleMarkContacted = async () => {
    try {
      setIsUpdatingLifecycle(true);
      setErrorMessage(null);
      await updateLeadMutation.mutateAsync({
        id: leadId,
        payload: { status: 'Contacted', expected_updated_at: lead?.updated_at },
      });
      await refreshLifecycle();
      setSuccessMessage('Lead marked as Contacted.');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to mark lead as Contacted.'));
    } finally {
      setIsUpdatingLifecycle(false);
    }
  };

  const handleAssignLead = async () => {
    if (!lead || !isAssignmentChanged) return;
    const isUnassigning = selectedAssignUser === UNASSIGNED_VALUE;
    try {
      setIsAssigning(true);
      if (isUnassigning) {
        await assignLeadApi(leadId, null);
      } else {
        await assignLeadApi(leadId, selectedAssignUser);
      }
      await refreshLifecycle();
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
    <div className="mx-auto w-full max-w-[1600px] space-y-5 pb-16 text-[#374151]">
      {/* Breadcrumb Navigation */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 px-1 text-caption font-medium text-[#6B7280] sm:px-0">
        <Link href="/leads" className="hover:text-[#2563EB] transition flex items-center gap-1">
          <ArrowLeft className="w-3.5 h-3.5" /> Leads
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-[#9CA3AF]" />
        <span className="text-[#111827] font-semibold truncate max-w-[200px] sm:max-w-none">
          {lead.contact_name}
        </span>
      </nav>

      {/* Primary record navigation stays visible while users move through a long detail page. */}
      <PageTabs
        value={activeTab}
        onValueChange={setActiveTab}
        detail
        sticky
        tabs={[
          { value: 'overview', icon: <Briefcase className="size-4" />, label: 'Overview & Details' },
          { value: 'timeline', icon: <History className="size-4" />, label: `Timeline (${timelinePageData?.total ?? 0})` },
          { value: 'notes', icon: <FileText className="size-4" />, label: `Notes (${notesPageData?.total ?? 0})` },
          { value: 'tasks', icon: <CheckSquare className="size-4" />, label: `Tasks (${tasksPageData?.total ?? 0})` },
          { value: 'emails', icon: <Send className="size-4" />, label: `Emails (${emailsPageData?.total ?? 0})` },
          ...(canReadCalls
            ? [{ value: 'calls' as const, icon: <PhoneCall className="size-4" />, label: `Calls (${callsPageData?.total ?? 0})` }]
            : []),
          { value: 'documents', icon: <Paperclip className="size-4" />, label: `Documents (${documentsPageData?.total ?? 0})` },
          { value: 'actions', icon: <Zap className="size-4" />, label: 'Actions & Convert' },
        ]}
      />

      {/* Success Banner */}
      {successMessage && (
        <Alert variant="default" className="bg-[#16A34A]/10 border-[#16A34A]/20 text-[#16A34A] font-medium animate-in fade-in-50">
          <CheckCircle2 className="h-4 w-4 text-[#16A34A] mr-2" />
          <AlertDescription className="text-[#16A34A] font-medium">
            {successMessage}
          </AlertDescription>
        </Alert>
      )}

      {errorMessage && !isModalOpen && !isEmailModalOpen && !isNoteModalOpen && !isTaskModalOpen && !isDocModalOpen && (
        <Alert variant="destructive" className="bg-rose-50 border-rose-300 text-rose-950 font-bold">
          <AlertCircle className="h-4 w-4 text-rose-600 mr-2" />
          <AlertDescription className="text-rose-900 font-bold text-xs">{errorMessage}</AlertDescription>
        </Alert>
      )}

      {/* Header Banner */}
      <div className="flex flex-col gap-5 rounded-card border border-[#E5E7EB] bg-white p-4 shadow-saas-sm sm:p-5 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 items-start gap-4 sm:items-center">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-btn bg-[#2563EB] text-xl font-semibold text-white shadow-saas-sm">
            {lead.contact_name ? lead.contact_name.charAt(0).toUpperCase() : 'L'}
          </div>
          <div className="min-w-0 space-y-1">
            <div className="flex items-center flex-wrap gap-2.5">
              <h1 className="text-page-title truncate text-[#111827]">
                {lead.contact_name}
              </h1>
              <span className="px-2.5 py-0.5 rounded-full bg-[#2563EB]/10 border border-[#2563EB]/20 text-[#2563EB] text-badge font-semibold">
                {lead.status}
              </span>
            </div>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-body font-medium text-[#6B7280]">
              <span className="truncate">{lead.title}</span>
              <span className="text-[#9CA3AF]" aria-hidden="true">•</span>
              <span className="text-[#2563EB] font-semibold">{lead.company}</span>
            </p>
          </div>
        </div>

        {/* Header Actions */}
        <div className="flex w-full shrink-0 flex-wrap items-center gap-2.5 md:w-auto">
          <Button
            type="button"
            variant="outline"
            size="default"
            onClick={handleOpenEditModal}
            className="text-button w-full font-medium cursor-pointer sm:w-auto"
          >
            <Pencil className="w-4 h-4 mr-2" /> Edit Lead
          </Button>
          <Button
            type="button"
            variant="outline"
            size="default"
            onClick={() => setIsDeleteModalOpen(true)}
            className="text-button w-full border-rose-200 font-medium text-rose-700 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-800 sm:w-auto"
          >
            <Trash2 className="w-4 h-4 mr-2" /> Delete Lead
          </Button>
        </div>
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

                <div className="flex items-center justify-between">
                  <span className="text-[#6B7280] font-medium flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-[#9CA3AF]" /> Next Follow-up
                  </span>
                  <span className="text-[#111827] font-medium">
                    {lead.next_follow_up_at
                      ? formatDateTime(lead.next_follow_up_at, { timeZone: leadTimeZone })
                      : 'Not scheduled'}
                  </span>
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

      {activeTab === 'timeline' && (
        <Card className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
          <div className="border-b border-slate-100 pb-3">
            <h3 className="flex items-center gap-2 text-sm font-black text-slate-950">
              <History className="h-4 w-4 text-indigo-600" /> Lead Activity Timeline
            </h3>
            <p className="mt-1 text-xs font-semibold text-slate-500">
              Lifecycle changes and linked CRM activity for this lead.
            </p>
          </div>
          {isTimelineLoading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-xs font-semibold text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading timeline...
            </div>
          ) : timeline.length === 0 ? (
            <p className="py-10 text-center text-xs font-semibold text-slate-500">
              No activity has been recorded for this lead.
            </p>
          ) : (
            <ol className="space-y-3">
              {timeline.map((event) => (
                <li key={event.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-col justify-between gap-1 sm:flex-row sm:items-start">
                    <div>
                      <p className="text-sm font-bold text-slate-900">{event.title}</p>
                      <p className="mt-1 text-xs text-slate-600">{event.description}</p>
                    </div>
                    <time className="shrink-0 text-xs font-medium text-slate-500">
                      {formatDateTime(event.timestamp, { timeZone: leadTimeZone })}
                    </time>
                  </div>
                </li>
              ))}
            </ol>
          )}
          {(timelinePageData?.total ?? 0) > relationPageSize && (
            <div className="flex items-center justify-between border-t border-slate-100 pt-4">
              <Button type="button" variant="outline" disabled={timelinePage === 1} onClick={() => setTimelinePage((page) => page - 1)}>Previous</Button>
              <span className="text-xs font-semibold text-slate-500">Page {timelinePage} of {Math.ceil((timelinePageData?.total ?? 0) / relationPageSize)}</span>
              <Button type="button" variant="outline" disabled={timelinePage * relationPageSize >= (timelinePageData?.total ?? 0)} onClick={() => setTimelinePage((page) => page + 1)}>Next</Button>
            </div>
          )}
        </Card>
      )}

      {/* 2. NOTES TAB */}
      {activeTab === 'notes' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-sm font-black uppercase tracking-wider text-slate-900 flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-600" /> Lead Notes ({notesPageData?.total ?? 0})
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

          <DataTable
            columns={noteColumns}
            data={notes}
            getRowKey={(note) => note.id}
            emptyTitle="No notes attached yet"
            emptyDescription="Use Add Note above to attach a note."
            isLoading={isNotesLoading}
            tableClassName="min-w-[560px]"
            className="shadow-none"
            pagination={{ pageIndex: notesPage - 1, pageCount: Math.max(1, Math.ceil((notesPageData?.total ?? 0) / relationPageSize)), onPageChange: (page) => setNotesPage(page + 1), totalRecords: notesPageData?.total ?? 0 }}
          />
        </Card>
      )}

      {/* 3. TASKS TAB */}
      {activeTab === 'tasks' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-sm font-black uppercase tracking-wider text-slate-900 flex items-center gap-2">
                <CheckSquare className="w-4 h-4 text-indigo-600" /> Assigned Lead Tasks ({tasksPageData?.total ?? 0})
              </h3>
              <p className="text-xs font-bold text-slate-500 mt-0.5">Tasks created for lead {lead.contact_name}</p>
            </div>
            <Button
              type="button"
              onClick={() => {
                setTaskErrorMessage(null);
                setIsTaskModalOpen(true);
              }}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-4 h-9 shadow-xs cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Create Task
            </Button>
          </div>

          <DataTable
            columns={taskColumns}
            data={tasks}
            getRowKey={(task) => task.id}
            emptyTitle="No tasks created for this lead yet"
            emptyDescription="Use Create Task above to assign a new task."
            isLoading={isTasksLoading}
            tableClassName="min-w-[560px]"
            className="shadow-none"
            pagination={{ pageIndex: tasksPage - 1, pageCount: Math.max(1, Math.ceil((tasksPageData?.total ?? 0) / relationPageSize)), onPageChange: (page) => setTasksPage(page + 1), totalRecords: tasksPageData?.total ?? 0 }}
          />
        </Card>
      )}

      {/* 4. EMAILS TAB */}
      {activeTab === 'emails' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-sm font-black uppercase tracking-wider text-slate-900 flex items-center gap-2">
                <Send className="w-4 h-4 text-indigo-600" /> Email History ({emailsPageData?.total ?? 0})
              </h3>
              <p className="text-xs font-bold text-slate-500 mt-0.5">Emails sent to lead {lead.contact_name}</p>
            </div>
            <Button
              type="button"
              onClick={() => {
                if (!isValidEmail(lead.email)) {
                  setErrorMessage('This lead does not have a valid email address.');
                  return;
                }
                setErrorMessage(null);
                setEmailTo(lead.email.trim());
                emailIdempotencyKeyRef.current = null;
                setIsEmailModalOpen(true);
              }}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-4 h-9 shadow-xs cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Send Email
            </Button>
          </div>

          <DataTable
            columns={emailColumns}
            data={emails}
            getRowKey={(email) => email.id}
            emptyTitle="No email communications logged yet"
            emptyDescription="Use Send Email above to send an email."
            isLoading={isEmailsLoading}
            expandableRow={(email) => (
              <div className="space-y-2">
                <EmailBodyPreview body={email.body} />
                {email.status === 'Failed' && email.failure_reason && (
                  <p className="text-xs font-medium text-rose-600">
                    Delivery failed: {email.failure_reason}
                  </p>
                )}
              </div>
            )}
            pagination={{ pageIndex: emailsPage - 1, pageCount: Math.max(1, Math.ceil((emailsPageData?.total ?? 0) / relationPageSize)), onPageChange: (page) => setEmailsPage(page + 1), totalRecords: emailsPageData?.total ?? 0 }}
          />
        </Card>
      )}

      {/* 5. CALLS TAB */}
      {activeTab === 'calls' && canReadCalls && (
        <LeadCallLogSection
          leadId={leadId}
          leadContactName={lead.contact_name}
          relatedContactId={lead.converted_contact_id}
          relatedCompanyId={lead.converted_company_id}
          relatedDealId={lead.converted_deal_id}
          calls={calls}
          isLoading={isCallsLoading}
          isError={isCallsError}
          error={callsError}
          onRetry={() => void refetchCalls()}
          timeZone={leadTimeZone}
          pagination={{ pageIndex: callsPage - 1, pageCount: Math.max(1, Math.ceil((callsPageData?.total ?? 0) / relationPageSize)), onPageChange: (page) => setCallsPage(page + 1), totalRecords: callsPageData?.total ?? 0 }}
        />
      )}

      {/* 6. DOCUMENTS TAB */}
      {activeTab === 'documents' && (
        <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-2xl space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-sm font-black uppercase tracking-wider text-slate-900 flex items-center gap-2">
                <Paperclip className="w-4 h-4 text-indigo-600" /> Attached Documents ({documentsPageData?.total ?? 0})
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

          <DataTable
            columns={documentColumns}
            data={documents}
            getRowKey={(document) => document.id}
            emptyTitle="No documents uploaded yet"
            emptyDescription="Use Upload Document above to attach a file."
            isLoading={isDocsLoading}
            tableClassName="min-w-[560px]"
            className="shadow-none"
            pagination={{ pageIndex: documentsPage - 1, pageCount: Math.max(1, Math.ceil((documentsPageData?.total ?? 0) / relationPageSize)), onPageChange: (page) => setDocumentsPage(page + 1), totalRecords: documentsPageData?.total ?? 0 }}
          />
        </Card>
      )}

      {/* 7. ACTIONS & CONVERT TAB */}
      {activeTab === 'actions' && (
        <div className="space-y-6">
          <Card className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
            <div className="border-b border-slate-100 pb-3">
              <h3 className="flex items-center gap-2 text-sm font-black text-slate-950">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" /> Lead Lifecycle
              </h3>
              <p className="mt-1 text-xs font-bold text-slate-600">
                Current status: {lead.status}. Lifecycle changes are validated and audited.
              </p>
            </div>
            <PermissionGate permission={PERMISSIONS.LEADS.UPDATE}>
              <div className="flex flex-wrap gap-3">
                {lead.status === 'New' && (
                  <Button type="button" onClick={handleMarkContacted} disabled={isUpdatingLifecycle}>
                    Mark Contacted
                  </Button>
                )}
                {(lead.status === 'New' || lead.status === 'Contacted') && (
                  <Button type="button" onClick={() => setLifecycleAction('qualify')} disabled={isUpdatingLifecycle} className="bg-emerald-600 text-white hover:bg-emerald-700">
                    Qualify Lead
                  </Button>
                )}
                {['New', 'Contacted', 'Qualified'].includes(lead.status) && (
                  <Button type="button" variant="outline" onClick={() => setLifecycleAction('disqualify')} disabled={isUpdatingLifecycle} className="border-rose-200 text-rose-700 hover:bg-rose-50">
                    Disqualify Lead
                  </Button>
                )}
                {lead.status === 'Unqualified' && (
                  <Button type="button" onClick={handleReopenLead} disabled={isUpdatingLifecycle}>
                    Reopen Lead
                  </Button>
                )}
                {lead.status === 'Converted' && (
                  <p className="text-xs font-semibold text-slate-600">This lead has completed conversion and is read-only.</p>
                )}
              </div>
            </PermissionGate>
          </Card>

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
              <PermissionGate permission={PERMISSIONS.LEADS.CONVERT}>
                <Button type="button" onClick={handleConvertLead} disabled={isConverting || lead.status !== 'Qualified' || Boolean(lead.is_archived)} className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs px-4 cursor-pointer">
                  {isConverting ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <ArrowRightLeft className="w-3.5 h-3.5 mr-1.5" />}
                  Convert Lead
                </Button>
              </PermissionGate>
            </div>
          </Card>

          <PermissionGate permission={PERMISSIONS.LEADS.ASSIGN}>
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
          </PermissionGate>

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
              <Textarea
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
            {taskErrorMessage && (
              <Alert id="lead-task-error" variant="destructive" className="bg-rose-50 border-rose-300 text-rose-950 font-bold">
                <AlertCircle className="h-4 w-4 text-rose-600 mr-2" />
                <AlertDescription className="text-rose-900 font-bold text-xs">{taskErrorMessage}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="lead-task-title" className="text-xs font-black text-black">Task Title *</Label>
              <Input id="lead-task-title" ref={taskTitleRef} required aria-invalid={Boolean(taskErrorMessage && !taskTitle.trim())} aria-describedby={taskErrorMessage ? 'lead-task-error' : undefined} placeholder="Schedule follow-up call" value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} className="bg-slate-50 border-slate-300 text-xs font-bold text-black" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-black text-black">Description</Label>
              <Input placeholder="Prepare pricing quotation and proposal deck" value={taskDesc} onChange={(e) => setTaskDesc(e.target.value)} className="bg-slate-50 border-slate-300 text-xs font-bold text-black" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-black text-black">Priority</Label>
              <ResponsiveSelect value={taskPriority} onValueChange={setTaskPriority} className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-slate-50 text-xs font-bold text-black">
                <option value="High">High</option>
                <option value="Medium">Medium</option>
                <option value="Low">Low</option>
              </ResponsiveSelect>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="lead-task-due-date" className="text-xs font-black text-black">Follow-up Due Date *</Label>
              <DateTimePicker
                triggerRef={taskDueDateRef}
                id="lead-task-due-date"
                required
                aria-describedby={taskErrorMessage ? 'lead-task-error' : undefined}
                aria-invalid={Boolean(taskErrorMessage && !taskDueDate)}
                value={taskDueDate}
                onValueChange={(value) => {
                  setTaskDueDate(value);
                  if (value) setTaskErrorMessage(null);
                }}
                className="bg-slate-50 border-slate-300 text-xs font-bold text-black"
              />
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
          {errorMessage && (
            <div className="pb-4">
              <Alert variant="destructive" className="bg-rose-50 border-rose-300 text-rose-950 font-bold">
                <AlertCircle className="h-4 w-4 text-rose-600 mr-2" />
                <AlertDescription className="text-rose-900 font-bold text-xs">{errorMessage}</AlertDescription>
              </Alert>
            </div>
          )}
          <form onSubmit={handleSendEmail} className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-black text-black">To</Label>
              <div className="rounded-xl border border-slate-300 bg-slate-50 px-3 py-2">
                <p className="text-xs font-black text-black">{lead.contact_name}</p>
                <p className="text-xs font-bold text-slate-600">{emailTo}</p>
              </div>
              <p className="text-[11px] font-medium text-slate-500">The Lead&apos;s primary email is used as the recipient.</p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-black text-black">Subject Line *</Label>
              <Input required maxLength={500} placeholder="Enterprise CRM Proposal & Next Steps" value={emailSubject} onChange={(e) => setEmailSubject(e.target.value)} className="bg-slate-50 border-slate-300 text-xs font-bold text-black" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-black text-black">Email Body</Label>
              <Textarea required maxLength={100000} rows={4} placeholder="Hi, following up on our recent demo..." value={emailBody} onChange={(e) => setEmailBody(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-xl bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500" />
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
              <Input
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

      {isModalOpen && lead && (
        <LeadFormDialog
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          lead={lead}
          onSaved={() => {
            setIsModalOpen(false);
            setSuccessMessage('Lead updated successfully!');
            window.setTimeout(() => setSuccessMessage(null), 4000);
            void queryClient.invalidateQueries({ queryKey: ['lead', lead.id] });
            void refetch();
          }}
        />
      )}

      {lifecycleAction && (
        <ModalShell
          isOpen={Boolean(lifecycleAction)}
          onClose={() => {
            if (!isUpdatingLifecycle) {
              setLifecycleAction(null);
              setLifecycleReason('');
            }
          }}
          size="md"
          title={lifecycleAction === 'qualify' ? 'Qualify Lead' : 'Disqualify Lead'}
        >
          <form onSubmit={handleLifecycleSubmit} className="space-y-4">
            <p className="text-sm text-slate-600">
              {lifecycleAction === 'qualify'
                ? 'Confirm that this lead meets your qualification criteria.'
                : 'Record why this lead is not currently qualified.'}
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="lead-lifecycle-reason" className="text-xs font-bold text-slate-900">
                Reason {lifecycleAction === 'disqualify' ? '*' : '(optional)'}
              </Label>
              <Textarea
                id="lead-lifecycle-reason"
                required={lifecycleAction === 'disqualify'}
                maxLength={2000}
                rows={4}
                value={lifecycleReason}
                onChange={(event) => setLifecycleReason(event.target.value)}
                placeholder="Add qualification context for the audit trail"
              />
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-100 pt-4">
              <Button type="button" variant="outline" onClick={() => setLifecycleAction(null)} disabled={isUpdatingLifecycle}>
                Cancel
              </Button>
              <Button type="submit" disabled={isUpdatingLifecycle} className={lifecycleAction === 'disqualify' ? 'bg-rose-600 text-white hover:bg-rose-700' : 'bg-emerald-600 text-white hover:bg-emerald-700'}>
                {isUpdatingLifecycle && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {lifecycleAction === 'qualify' ? 'Qualify Lead' : 'Disqualify Lead'}
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
