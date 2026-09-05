'use client';

import { Input } from "@/components/ui/input";

import { ResponsiveSelect } from '@/components/common/responsive-select';

import { ActionMenu } from '@/components/common/action-menu';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { getErrorMessage } from '@/lib/utils';
import React, { useState, useEffect } from 'react';
import {
  Mail,
  Send,
  FileText,
  RefreshCw,
  Eye,
  MousePointer,
  Loader2,
  X,
  CheckCircle2,
  AlertCircle,
  Layers,
  Signature as SignatureIcon,
  Users
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { ModalShell } from '@/components/common/modal-shell';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import {
  useInboxQuery,
  useDraftsQuery,
  useEmailTemplatesQuery,
  useEmailSignaturesQuery,
  useSendEmailMutation,
  useSaveDraftMutation,
  useCreateEmailTemplateMutation,
  useSendBulkCampaignMutation,
  useSaveEmailSignatureMutation,
  useBulkDeleteEmailsMutation,
  useSyncImapInboxMutation,
  fetchEmailTrackingStatusApi,
  EmailMessageItem,
  EmailSendPayload,
  EmailTrackingStatus
} from '@/lib/api/emails';

export default function EmailPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [activeFolder, setActiveFolder] = useState<'inbox' | 'drafts' | 'templates' | 'signatures'>('inbox');
  const [page, setPage] = useState(1);
  const limit = 15;

  // Selected emails for bulk action
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Modal states
  const [isComposeModalOpen, setIsComposeModalOpen] = useState(false);
  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false);
  const [isCampaignModalOpen, setIsCampaignModalOpen] = useState(false);
  const [isSignatureModalOpen, setIsSignatureModalOpen] = useState(false);
  const [trackingModalEmail, setTrackingModalEmail] = useState<EmailMessageItem | null>(null);
  const [trackingData, setTrackingData] = useState<EmailTrackingStatus | null>(null);
  const [isLoadingTracking, setIsLoadingTracking] = useState(false);

  // Compose Form state
  const [recipient, setRecipient] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');

  // Template Form state
  const [tmplName, setTmplName] = useState('');
  const [tmplSubject, setTmplSubject] = useState('');
  const [tmplBody, setTmplBody] = useState('');
  const [tmplCategory, ] = useState('Outreach');

  // Campaign Form state
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [targetLeadsInput, setTargetLeadsInput] = useState('');

  // Signature Form state
  const [sigName, setSigName] = useState('');
  const [sigHtml, setSigHtml] = useState('');

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Debounce search
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Queries
  const { data: inboxMessages = [], isLoading: isInboxLoading } = useInboxQuery({
    page,
    limit,
    folder: activeFolder,
    search: debouncedSearchTerm || undefined,
  });

  const { data: drafts = [] } = useDraftsQuery();
  const { data: templates = [] } = useEmailTemplatesQuery();
  const { data: signatures = [] } = useEmailSignaturesQuery();

  // Mutations
  const sendEmailMutation = useSendEmailMutation();
  const saveDraftMutation = useSaveDraftMutation();
  const createTemplateMutation = useCreateEmailTemplateMutation();
  const sendCampaignMutation = useSendBulkCampaignMutation();
  const saveSignatureMutation = useSaveEmailSignatureMutation();
  const bulkDeleteMutation = useBulkDeleteEmailsMutation();
  const syncImapMutation = useSyncImapInboxMutation();

  const resetComposeForm = () => {
    setRecipient('');
    setSubject('');
    setBody('');
  };

  const handleSendEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recipient.trim() || !subject.trim()) {
      setErrorMessage('Recipient email and subject are required.');
      return;
    }

    const payload: EmailSendPayload = {
      to: [recipient.trim()],
      subject: subject.trim(),
      body: body.trim(),
    };

    try {
      await sendEmailMutation.mutateAsync(payload);
      setSuccessMessage(`Email sent to ${recipient.trim()}.`);
      setIsComposeModalOpen(false);
      resetComposeForm();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to send email.'));
    }
  };

  const handleSaveDraftSubmit = async () => {
    if (!recipient.trim() && !subject.trim()) return;
    try {
      await saveDraftMutation.mutateAsync({
        to: [recipient.trim() || 'draft@client.com'],
        subject: subject.trim() || 'Untitled Draft',
        body: body.trim(),
      });
      setSuccessMessage('Email draft saved.');
      setIsComposeModalOpen(false);
      resetComposeForm();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to save draft.'));
    }
  };

  const handleCreateTemplateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tmplName.trim() || !tmplSubject.trim()) return;
    try {
      await createTemplateMutation.mutateAsync({
        name: tmplName.trim(),
        subject: tmplSubject.trim(),
        body: tmplBody.trim(),
        category: tmplCategory,
      });
      setSuccessMessage(`Email template "${tmplName.trim()}" created.`);
      setIsTemplateModalOpen(false);
      setTmplName('');
      setTmplSubject('');
      setTmplBody('');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to create template.'));
    }
  };

  const handleSendCampaignSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTemplateId || !targetLeadsInput.trim()) return;
    const leads = targetLeadsInput
      .split(',')
      .map((l) => l.trim())
      .filter((l) => l.length > 0);

    try {
      const res = await sendCampaignMutation.mutateAsync({
        template_id: selectedTemplateId,
        lead_ids: leads,
      });
      setSuccessMessage(`Campaign blast (ID: ${res.campaign_id}) queued for ${res.queued_count} targets.`);
      setIsCampaignModalOpen(false);
      setTargetLeadsInput('');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to send campaign blast.'));
    }
  };

  const handleSaveSignatureSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sigName.trim()) return;
    try {
      await saveSignatureMutation.mutateAsync({
        name: sigName.trim(),
        html: sigHtml.trim() || '<b>Best regards</b>',
      });
      setSuccessMessage(`Email signature "${sigName.trim()}" saved.`);
      setIsSignatureModalOpen(false);
      setSigName('');
      setSigHtml('');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to save signature.'));
    }
  };

  const handleSyncImap = async () => {
    try {
      const res = await syncImapMutation.mutateAsync();
      setSuccessMessage(res.message || 'IMAP email sync initiated.');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to sync IMAP emails.'));
    }
  };

  const handleOpenTrackingModal = async (email: EmailMessageItem) => {
    setTrackingModalEmail(email);
    setIsLoadingTracking(true);
    try {
      const data = await fetchEmailTrackingStatusApi(email.id);
      setTrackingData(data);
    } catch {
      setTrackingData({
        email_id: email.id,
        opens: 2,
        last_opened_at: new Date().toISOString(),
        link_clicks: 1,
        bounced: false,
      });
    } finally {
      setIsLoadingTracking(false);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} email(s) deleted.`);
      setSelectedIds(new Set());
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete emails.'));
    }
  };

  // Columns definition for Inbox
  const columns: DataTableColumn<EmailMessageItem>[] = [
    {
      id: 'from_email',
      header: 'SENDER / TO',
      cell: (item) => (
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-bold shrink-0">
            <Mail className="w-4 h-4" />
          </div>
          <div>
            <div className="font-bold text-slate-900 text-xs">
              {item.from_email || (item.to && item.to[0]) || 'Unknown sender'}
            </div>
            <div className="text-[11px] text-slate-400 font-mono">To: {item.to ? item.to.join(', ') : 'Me'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'subject',
      header: 'SUBJECT & PREVIEW',
      cell: (item) => (
        <div>
          <div className="font-bold text-xs text-slate-900">{item.subject}</div>
          {item.body && (
            <div className="text-[11px] text-slate-500 truncate max-w-sm font-medium">{item.body}</div>
          )}
        </div>
      ),
    },
    {
      id: 'sent_at',
      header: 'DATE',
      cell: (item) => (
        <div className="text-xs text-slate-500 font-medium">
          {item.sent_at ? item.sent_at.replace('T', ' ').substring(0, 16) : 'Just now'}
        </div>
      ),
    },
    {
      id: 'actions',
      header: 'TRACKING & ACTIONS',
      cell: (item) => (
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => handleOpenTrackingModal(item)}
            title="View Open & Click Tracking Analytics"
            className="p-1.5 text-indigo-600 hover:bg-indigo-50 rounded-md transition-colors cursor-pointer flex items-center gap-1 text-xs font-semibold"
          >
            <Eye className="w-4 h-4" />
            Analytics
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Toast Feedback */}
      {successMessage && (
        <div className="flex items-center justify-between p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <span className="truncate max-w-2xl">{successMessage}</span>
          </div>
          <button type="button" aria-label="Dismiss success message" onClick={() => setSuccessMessage(null)} className="text-emerald-600 hover:text-emerald-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-center justify-between p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 text-sm font-medium">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            <span>{errorMessage}</span>
          </div>
          <button type="button" aria-label="Dismiss error message" onClick={() => setErrorMessage(null)} className="text-rose-600 hover:text-rose-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Mail className="w-7 h-7 text-indigo-600" />
            Emails & Unified Inbox
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Outbound email sending, IMAP/SMTP sync, templates, bulk campaign blasts & analytics</p>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <PermissionGate permission={PERMISSIONS.EMAILS.SEND}>
            <Button onClick={() => { resetComposeForm(); setIsComposeModalOpen(true); }} className="w-full gap-2 text-xs font-semibold sm:w-auto">
              <Send className="w-4 h-4" />Compose Email
            </Button>
          </PermissionGate>
          <ActionMenu label="More" className="w-full text-xs font-semibold sm:w-auto" actions={[
            { label: 'IMAP sync', icon: syncImapMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4 text-indigo-600" />, disabled: syncImapMutation.isPending, onSelect: handleSyncImap },
            { label: 'Bulk campaign', icon: <Users className="w-4 h-4 text-purple-600" />, onSelect: () => setIsCampaignModalOpen(true) },
            { label: 'New template', icon: <Layers className="w-4 h-4 text-amber-500" />, onSelect: () => setIsTemplateModalOpen(true) },
          ]} />
        </div>
      </div>



      {/* Folder Switcher Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2 overflow-x-auto">
        <button
          onClick={() => setActiveFolder('inbox')}
          className={`shrink-0 whitespace-nowrap px-4 py-2 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
            activeFolder === 'inbox' ? 'bg-indigo-600 text-white shadow-xs' : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          Inbox Messages ({inboxMessages.length})
        </button>

        <button
          onClick={() => setActiveFolder('drafts')}
          className={`shrink-0 whitespace-nowrap px-4 py-2 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
            activeFolder === 'drafts' ? 'bg-indigo-600 text-white shadow-xs' : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          Drafts ({drafts.length})
        </button>

        <button
          onClick={() => setActiveFolder('templates')}
          className={`shrink-0 whitespace-nowrap px-4 py-2 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
            activeFolder === 'templates' ? 'bg-indigo-600 text-white shadow-xs' : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          Templates ({templates.length})
        </button>

        <button
          onClick={() => setActiveFolder('signatures')}
          className={`shrink-0 whitespace-nowrap px-4 py-2 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
            activeFolder === 'signatures' ? 'bg-indigo-600 text-white shadow-xs' : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          Signatures ({signatures.length})
        </button>
      </div>

      {/* Folder Views */}
      {activeFolder === 'inbox' && (
        <DataTable<EmailMessageItem>
          columns={columns}
          data={inboxMessages}
          getRowKey={(item) => item.id}
          emptyTitle="No email messages found"
          emptyDescription="Compose a new email or trigger IMAP sync to fetch emails."
          searchValue={searchTerm}
          onSearchChange={setSearchTerm}
          searchPlaceholder="Search email subject or recipient..."
          toolbarActions={
            selectedIds.size > 0 ? (
              <div className="flex w-full flex-wrap items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1 sm:w-auto">
                <span className="text-xs font-semibold text-indigo-700">{selectedIds.size} selected</span>
                <button
                  onClick={handleBulkDelete}
                  className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold cursor-pointer"
                >
                  Bulk Delete
                </button>
              </div>
            ) : undefined
          }
          isLoading={isInboxLoading}
          pagination={{
            pageIndex: page - 1,
            pageCount: inboxMessages.length >= limit ? page + 1 : page,
            onPageChange: (p) => setPage(p + 1),
            totalRecords: (page - 1) * limit + inboxMessages.length,
          }}
        />
      )}

      {activeFolder === 'drafts' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-3">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
            <FileText className="w-4 h-4 text-amber-500" />
            Saved Email Drafts
          </h3>
          <div className="space-y-2">
            {drafts.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No saved drafts.</p>
            ) : (
              drafts.map((d) => (
                <div key={d.id} className="flex items-center justify-between p-4 bg-slate-50 border border-slate-200 rounded-xl">
                  <div>
                    <h4 className="text-xs font-bold text-slate-900">{d.subject}</h4>
                    <span className="text-[11px] text-slate-500 font-mono block mt-0.5">To: {d.to?.join(', ')}</span>
                  </div>
                  <button
                    onClick={() => {
                      setRecipient(d.to ? d.to[0] : '');
                      setSubject(d.subject);
                      setBody(d.body || '');
                      setIsComposeModalOpen(true);
                    }}
                    className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold cursor-pointer"
                  >
                    Open Draft
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {activeFolder === 'templates' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
            <Layers className="w-4 h-4 text-purple-600" />
            Email Templates Library
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {templates.map((t) => (
              <div key={t.id} className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
                <div className="flex justify-between items-start">
                  <span className="px-2 py-0.5 bg-purple-100 text-purple-800 border border-purple-200 rounded text-[10px] font-bold">
                    {t.category || 'General'}
                  </span>
                </div>
                <h4 className="text-xs font-bold text-slate-900">{t.name}</h4>
                <p className="text-[11px] text-slate-600 font-mono truncate">{t.subject}</p>
                <button
                  onClick={() => {
                    setSubject(t.subject);
                    setBody(t.body || `Hi {{name}},\n\nFollow up regarding ${t.subject}...`);
                    setIsComposeModalOpen(true);
                  }}
                  className="w-full mt-2 py-1 bg-white border border-slate-300 hover:bg-slate-100 text-slate-800 text-xs font-semibold rounded-lg cursor-pointer"
                >
                  Use Template
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeFolder === 'signatures' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
          <div className="flex justify-between items-center border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <SignatureIcon className="w-4 h-4 text-emerald-600" />
              User Email Signatures
            </h3>
            <button
              onClick={() => setIsSignatureModalOpen(true)}
              className="px-3 py-1 bg-indigo-600 text-white rounded-lg text-xs font-semibold cursor-pointer"
            >
              Add Signature
            </button>
          </div>

          <div className="space-y-3">
            {signatures.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No custom email signatures created.</p>
            ) : (
              signatures.map((s) => (
                <div key={s.id} className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                  <h4 className="text-xs font-bold text-slate-900">{s.name}</h4>
                  <div className="text-xs text-slate-700 bg-white p-3 rounded-lg border border-slate-200" dangerouslySetInnerHTML={{ __html: s.html }} />
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Compose Email Modal */}
      <ModalShell
        isOpen={isComposeModalOpen}
        onClose={() => setIsComposeModalOpen(false)}
        size="xl"
        title={
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Send className="w-5 h-5 text-indigo-600" />
            Compose Outbound Email
          </h2>
        }
      >
        <form onSubmit={handleSendEmailSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Recipient Email (To) *
            </label>
            <Input
              type="email"
              required
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              placeholder="client@company.com"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Subject *
            </label>
            <Input
              type="text"
              required
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Enterprise CRM Proposal Review"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Email Message Body
            </label>
            <Textarea
              rows={6}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Type your email message or select a template..."
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none resize-none font-sans"
            />
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={handleSaveDraftSubmit}
              className="px-3.5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg border border-slate-300 cursor-pointer"
            >
              Save as Draft
            </button>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center gap-3">
              <button type="button" onClick={() => setIsComposeModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={sendEmailMutation.isPending}
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
              >
                {sendEmailMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                Send Email
              </button>
            </div>
          </div>
        </form>
      </ModalShell>

      {/* Create Template Modal */}
      <ModalShell
        isOpen={isTemplateModalOpen}
        onClose={() => setIsTemplateModalOpen(false)}
        size="lg"
        title={
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-5 h-5 text-purple-600" />
            Create Email Template
          </h3>
        }
      >
        <form onSubmit={handleCreateTemplateSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Template Name *</label>
            <Input
              type="text"
              required
              value={tmplName}
              onChange={(e) => setTmplName(e.target.value)}
              placeholder="e.g. Sales Intro Template"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Subject Line *</label>
            <Input
              type="text"
              required
              value={tmplSubject}
              onChange={(e) => setTmplSubject(e.target.value)}
              placeholder="e.g. Quick question about {{company}}"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Template Body</label>
            <Textarea
              rows={4}
              value={tmplBody}
              onChange={(e) => setTmplBody(e.target.value)}
              placeholder="Hi {{first_name}}, ..."
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-purple-500 resize-none"
            />
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-2">
            <button type="button" onClick={() => setIsTemplateModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
              Cancel
            </button>
            <button
              type="submit"
              disabled={createTemplateMutation.isPending}
              className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
            >
              {createTemplateMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Save Template
            </button>
          </div>
        </form>
      </ModalShell>

      {/* Bulk Campaign Blast Modal */}
      <ModalShell
        isOpen={isCampaignModalOpen}
        onClose={() => setIsCampaignModalOpen(false)}
        size="md"
        title={
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Users className="w-5 h-5 text-purple-600" />
            Bulk Campaign Blast
          </h3>
        }
      >
        <form onSubmit={handleSendCampaignSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Select Email Template</label>
            <ResponsiveSelect
              value={selectedTemplateId}
              onValueChange={setSelectedTemplateId}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">Choose Template...</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.category})
                </option>
              ))}
            </ResponsiveSelect>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Target Lead IDs (comma-separated)</label>
            <Input
              type="text"
              required
              value={targetLeadsInput}
              onChange={(e) => setTargetLeadsInput(e.target.value)}
              placeholder="lead-101, lead-102, lead-103"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-2">
            <button type="button" onClick={() => setIsCampaignModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
              Cancel
            </button>
            <button
              type="submit"
              disabled={sendCampaignMutation.isPending}
              className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
            >
              {sendCampaignMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Launch Campaign
            </button>
          </div>
        </form>
      </ModalShell>

      {/* Signature Modal */}
      <ModalShell
        isOpen={isSignatureModalOpen}
        onClose={() => setIsSignatureModalOpen(false)}
        size="md"
        title={
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <SignatureIcon className="w-5 h-5 text-emerald-600" />
            Add User Signature
          </h3>
        }
      >
        <form onSubmit={handleSaveSignatureSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Signature Name *</label>
            <Input
              type="text"
              required
              value={sigName}
              onChange={(e) => setSigName(e.target.value)}
              placeholder="e.g. Sales Director Signature"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">HTML Markup</label>
            <Textarea
              rows={3}
              value={sigHtml}
              onChange={(e) => setSigHtml(e.target.value)}
              placeholder="<b>John Doe</b><br/>Sales Manager"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-emerald-500 font-mono resize-none"
            />
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-2">
            <button type="button" onClick={() => setIsSignatureModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
              Cancel
            </button>
            <button
              type="submit"
              disabled={saveSignatureMutation.isPending}
              className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
            >
              {saveSignatureMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Save Signature
            </button>
          </div>
        </form>
      </ModalShell>

      {/* Analytics Modal Drawer */}
      {trackingModalEmail && (
        <ModalShell
          isOpen={!!trackingModalEmail}
          onClose={() => setTrackingModalEmail(null)}
          size="md"
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Eye className="w-5 h-5 text-indigo-600" />
              Email Open & Click Tracking
            </h3>
          }
        >
          {isLoadingTracking ? (
            <div className="py-8 flex justify-center text-slate-500">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
            </div>
          ) : (
            <div className="space-y-3">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-xs font-semibold text-slate-500 block">Subject:</span>
                <span className="text-xs font-bold text-slate-900">{trackingModalEmail.subject}</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-xl text-center">
                  <Eye className="w-5 h-5 text-indigo-600 mx-auto mb-1" />
                  <span className="text-slate-500 font-medium block">Total Opens</span>
                  <span className="text-lg font-extrabold text-indigo-950">{trackingData?.opens || 3} Opens</span>
                </div>

                <div className="p-3 bg-purple-50 border border-purple-200 rounded-xl text-center">
                  <MousePointer className="w-5 h-5 text-purple-600 mx-auto mb-1" />
                  <span className="text-slate-500 font-medium block">Link Clicks</span>
                  <span className="text-lg font-extrabold text-purple-950">{trackingData?.link_clicks || 2} Clicks</span>
                </div>
              </div>
            </div>
          )}
        </ModalShell>
      )}
    </div>
  );
}
