'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Phone,
  PhoneCall,
  PhoneForwarded,
  PhoneIncoming,
  PhoneOutgoing,
  Clock,
  Plus,
  Search,
  Trash2,
  Volume2,
  Sparkles,
  Loader2,
  X,
  CheckCircle2,
  AlertCircle,
  FileText,
  Tag,
  Voicemail,
  TrendingUp,
  UserCheck
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import {
  useCallsQuery,
  useCallDispositionsQuery,
  useRepPerformanceStatsQuery,
  useLogCallMutation,
  useTriggerOutboundCallMutation,
  useCreateDispositionMutation,
  useLogVoicemailDropMutation,
  useDeleteCallMutation,
  useBulkDeleteCallsMutation,
  CallLogItem,
  CallLogBasePayload
} from '@/lib/api/calls';

export default function CallsPage() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [callTypeFilter, setCallTypeFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const limit = 15;

  // Selection for bulk actions
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Modal states
  const [isLogCallModalOpen, setIsLogCallModalOpen] = useState(false);
  const [isDialModalOpen, setIsDialModalOpen] = useState(false);
  const [isVoicemailModalOpen, setIsVoicemailModalOpen] = useState(false);
  const [isDispositionModalOpen, setIsDispositionModalOpen] = useState(false);
  const [callToDelete, setCallToDelete] = useState<CallLogItem | null>(null);

  // Form states
  const [contactId, setContactId] = useState('');
  const [callType, setCallType] = useState('Outbound');
  const [durationMinutes, setDurationMinutes] = useState('2');
  const [notes, setNotes] = useState('');

  // Click-to-dial form
  const [phoneNumber, setPhoneNumber] = useState('');

  // Voicemail drop form
  const [voicemailContactId, setVoicemailContactId] = useState('');
  const [voicemailTemplateId, setVoicemailTemplateId] = useState('vm-template-1');

  // Disposition tag form
  const [newDispositionName, setNewDispositionName] = useState('');

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
  const { data: calls = [], isLoading, refetch } = useCallsQuery({
    page,
    limit,
    search: debouncedSearchTerm || undefined,
    call_type: callTypeFilter || undefined,
  });

  const { data: dispositions = [] } = useCallDispositionsQuery();
  const { data: repStats = [] } = useRepPerformanceStatsQuery();

  // Mutations
  const logCallMutation = useLogCallMutation();
  const triggerDialMutation = useTriggerOutboundCallMutation();
  const createDispositionMutation = useCreateDispositionMutation();
  const voicemailDropMutation = useLogVoicemailDropMutation();
  const deleteCallMutation = useDeleteCallMutation();
  const bulkDeleteMutation = useBulkDeleteCallsMutation();

  const resetLogForm = () => {
    setContactId('');
    setCallType('Outbound');
    setDurationMinutes('2');
    setNotes('');
  };

  const handleLogCallSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const duration = parseInt(durationMinutes || '0', 10) * 60;
    const payload: CallLogBasePayload = {
      contact_id: contactId.trim() || 'Contact-101',
      call_type: callType,
      duration_seconds: duration,
      notes: notes.trim() || undefined,
    };

    try {
      await logCallMutation.mutateAsync(payload);
      setSuccessMessage('Call logged successfully.');
      setIsLogCallModalOpen(false);
      resetLogForm();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to log call.');
    }
  };

  const handleTriggerDialSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phoneNumber.trim()) return;
    try {
      const res = await triggerDialMutation.mutateAsync({
        phone_number: phoneNumber.trim(),
        contact_id: contactId.trim() || 'c-101',
      });
      setSuccessMessage(`Click-to-dial initiated (Call SID: ${res.call_sid}) to ${res.to}`);
      setIsDialModalOpen(false);
      setPhoneNumber('');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to initiate dial.');
    }
  };

  const handleVoicemailDropSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await voicemailDropMutation.mutateAsync({
        contact_id: voicemailContactId.trim() || 'c-101',
        voicemail_template_id: voicemailTemplateId,
      });
      setSuccessMessage(`Voicemail drop executed for contact.`);
      setIsVoicemailModalOpen(false);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to execute voicemail drop.');
    }
  };

  const handleCreateDispositionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDispositionName.trim()) return;
    try {
      await createDispositionMutation.mutateAsync(newDispositionName.trim());
      setSuccessMessage(`Disposition tag "${newDispositionName.trim()}" created.`);
      setNewDispositionName('');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to create disposition tag.');
    }
  };

  const handleDeleteCall = async () => {
    if (!callToDelete) return;
    try {
      await deleteCallMutation.mutateAsync(callToDelete.id);
      setSuccessMessage('Call log deleted successfully.');
      setCallToDelete(null);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete call log.');
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} call log(s) deleted.`);
      setSelectedIds(new Set());
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete selected call logs.');
    }
  };

  // Format duration
  const formatDuration = (seconds?: number) => {
    if (!seconds) return '0m 0s';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
  };

  // Columns definition
  const columns: DataTableColumn<CallLogItem>[] = [
    {
      id: 'call_type',
      header: 'CALL TYPE',
      cell: (item) => {
        const isOutbound = item.call_type !== 'Inbound';
        return (
          <div className="flex items-center gap-2.5">
            <div className={`h-8 w-8 rounded-lg flex items-center justify-center font-bold text-xs ${isOutbound ? 'bg-indigo-50 text-indigo-600 border border-indigo-100' : 'bg-emerald-50 text-emerald-600 border border-emerald-100'}`}>
              {isOutbound ? <PhoneOutgoing className="w-4 h-4" /> : <PhoneIncoming className="w-4 h-4" />}
            </div>
            <span className="font-bold text-xs text-slate-800">{item.call_type || 'Outbound'}</span>
          </div>
        );
      },
    },
    {
      id: 'contact_id',
      header: 'CONTACT',
      cell: (item) => (
        <div>
          <div
            onClick={(e) => {
              e.stopPropagation();
              router.push(`/calls/${item.id}`);
            }}
            className="font-bold text-slate-900 hover:text-indigo-600 cursor-pointer transition-colors text-xs"
          >
            {item.contact_id || 'Client Contact'}
          </div>
          <div className="text-[11px] text-slate-400 font-mono">ID: {item.id.substring(0, 8)}...</div>
        </div>
      ),
    },
    {
      id: 'duration_seconds',
      header: 'DURATION',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-semibold">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span>{formatDuration(item.duration_seconds)}</span>
        </div>
      ),
    },
    {
      id: 'notes',
      header: 'CALL NOTES & DISPOSITION',
      cell: (item) => (
        <div className="text-xs text-slate-700 max-w-xs truncate font-medium">
          {item.notes || 'No call notes recorded.'}
        </div>
      ),
    },
    {
      id: 'timestamp',
      header: 'TIMESTAMP',
      cell: (item) => (
        <div className="text-xs text-slate-500 font-medium">
          {item.timestamp ? item.timestamp.replace('T', ' ').substring(0, 16) : 'Just now'}
        </div>
      ),
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (item) => (
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => router.push(`/calls/${item.id}`)}
            title="View Call Audio & AI Sentiment"
            className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-slate-100 rounded-md transition-colors cursor-pointer flex items-center gap-1 text-xs font-semibold"
          >
            <Volume2 className="w-4 h-4 text-indigo-600" />
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
          </button>
          <button
            onClick={() => setCallToDelete(item)}
            title="Delete Call Log"
            className="p-1.5 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
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
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-600 hover:text-emerald-800">
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
          <button onClick={() => setErrorMessage(null)} className="text-rose-600 hover:text-rose-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <PhoneCall className="w-7 h-7 text-indigo-600" />
            Call Logs & Telephony
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Click-to-dial via Twilio, log call notes, drop voicemails & AI sentiment analysis</p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => setIsDialModalOpen(true)}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-3.5 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            <PhoneOutgoing className="w-4 h-4" />
            Click to Dial
          </button>

          <button
            onClick={() => setIsVoicemailModalOpen(true)}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            <Voicemail className="w-4 h-4 text-indigo-600" />
            Voicemail Drop
          </button>

          <button
            onClick={() => setIsDispositionModalOpen(true)}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            <Tag className="w-4 h-4 text-amber-500" />
            Dispositions ({dispositions.length})
          </button>

          <PermissionGate permission={PERMISSIONS.CALLS.CREATE}>
            <button
              onClick={() => {
                resetLogForm();
                setIsLogCallModalOpen(true);
              }}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition-colors shadow-sm cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              Log Call
            </button>
          </PermissionGate>
        </div>
      </div>



      {/* Main Data Table */}
      <DataTable<CallLogItem>
        columns={columns}
        data={calls}
        getRowKey={(item) => item.id}
        onRowClick={(item) => router.push(`/calls/${item.id}`)}
        emptyTitle="No call logs found"
        emptyDescription="Initiate a click-to-dial call or manually record a call log."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search call notes..."
        toolbarActions={
          selectedIds.size > 0 ? (
            <div className="flex items-center gap-2 bg-indigo-50 px-3 py-1 rounded-lg border border-indigo-200">
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
        isLoading={isLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: calls.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + calls.length,
        }}
      />

      {/* Log Call Modal */}
      {isLogCallModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-5">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <PhoneCall className="w-5 h-5 text-indigo-600" />
                Log Call Details
              </h2>
              <button onClick={() => setIsLogCallModalOpen(false)} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleLogCallSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Contact / Client Name or ID
                </label>
                <input
                  type="text"
                  value={contactId}
                  onChange={(e) => setContactId(e.target.value)}
                  placeholder="e.g. John Doe or contact-123"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                    Call Direction
                  </label>
                  <select
                    value={callType}
                    onChange={(e) => setCallType(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                  >
                    <option value="Outbound">Outbound</option>
                    <option value="Inbound">Inbound</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                    Duration (Minutes)
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={durationMinutes}
                    onChange={(e) => setDurationMinutes(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Call Notes & Outcome
                </label>
                <textarea
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Discussed contract terms and scheduled a demo..."
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none resize-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button type="button" onClick={() => setIsLogCallModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={logCallMutation.isPending}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
                >
                  {logCallMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                  Save Call Log
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Click-to-Dial Modal */}
      {isDialModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <PhoneOutgoing className="w-5 h-5 text-emerald-600" />
                Twilio Click-to-Dial
              </h3>
              <button onClick={() => setIsDialModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleTriggerDialSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Phone Number *</label>
                <input
                  type="tel"
                  required
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="+1 (555) 234-5678"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setIsDialModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={triggerDialMutation.isPending}
                  className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
                >
                  {triggerDialMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Initiate Call
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Voicemail Drop Modal */}
      {isVoicemailModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Voicemail className="w-5 h-5 text-indigo-600" />
                Voicemail Drop Execution
              </h3>
              <button onClick={() => setIsVoicemailModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleVoicemailDropSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Target Contact ID or Name</label>
                <input
                  type="text"
                  value={voicemailContactId}
                  onChange={(e) => setVoicemailContactId(e.target.value)}
                  placeholder="e.g. contact-101"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Select Voicemail Template</label>
                <select
                  value={voicemailTemplateId}
                  onChange={(e) => setVoicemailTemplateId(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="vm-template-1">Follow-up Call Audio Drop #1</option>
                  <option value="vm-template-2">Product Pitch Voicemail #2</option>
                </select>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setIsVoicemailModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={voicemailDropMutation.isPending}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
                >
                  {voicemailDropMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Execute Drop
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Dispositions Modal */}
      {isDispositionModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Tag className="w-5 h-5 text-amber-500" />
                Call Dispositions
              </h3>
              <button onClick={() => setIsDispositionModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex flex-wrap gap-2 p-3 bg-slate-50 rounded-xl border border-slate-200">
              {dispositions.map((d, idx) => (
                <span key={idx} className="px-2.5 py-1 bg-white border border-slate-300 rounded-lg text-xs font-semibold text-slate-800 shadow-xs">
                  {d}
                </span>
              ))}
            </div>

            <form onSubmit={handleCreateDispositionSubmit} className="space-y-3 pt-2 border-t border-slate-100">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">Add New Disposition Tag</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newDispositionName}
                  onChange={(e) => setNewDispositionName(e.target.value)}
                  placeholder="e.g. Follow-up Needed"
                  className="flex-1 bg-slate-50 border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-amber-500"
                />
                <button
                  type="submit"
                  disabled={createDispositionMutation.isPending}
                  className="bg-amber-600 hover:bg-amber-700 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
                >
                  Add
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirm Delete Modal */}
      {callToDelete && (
        <ConfirmModal
          isOpen={!!callToDelete}
          title="Delete Call Log"
          description={`Are you sure you want to delete this call log?`}
          confirmText="Delete Call Log"
          variant="danger"
          onConfirm={handleDeleteCall}
          onClose={() => setCallToDelete(null)}
        />
      )}
    </div>
  );
}
