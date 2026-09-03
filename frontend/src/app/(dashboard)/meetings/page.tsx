'use client';

import { ActionMenu } from '@/components/common/action-menu';
import { Button } from '@/components/ui/button';
import { getErrorMessage } from '@/lib/utils';
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Video,
  Calendar,
  Clock,
  Plus,
  Download,
  Trash2,
  ExternalLink,
  Users,
  Sparkles,
  Loader2,
  X,
  CheckCircle2,
  AlertCircle,
  FileText,
  Share2
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import {
  useMeetingsQuery,
  useUpcomingMeetingsQuery,
  useCreateMeetingMutation,
  useCancelMeetingMutation,
  useBulkCancelMeetingsMutation,
  useCreateZoomLinkMutation,
  useCreateTeamsLinkMutation,
  useRescheduleMeetingMutation,
  exportIcalFeedApi,
  MeetingItem,
  MeetingCreatePayload
} from '@/lib/api/meetings';

export default function MeetingsPage() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const limit = 15;

  // Selected rows for bulk action
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isZoomModalOpen, setIsZoomModalOpen] = useState(false);
  const [isTeamsModalOpen, setIsTeamsModalOpen] = useState(false);
  const [meetingToDelete, setMeetingToDelete] = useState<MeetingItem | null>(null);
  const [rescheduleMeeting, setRescheduleMeeting] = useState<MeetingItem | null>(null);

  // Form states for Create Meeting
  const [title, setTitle] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [attendeesInput, setAttendeesInput] = useState('');
  const [meetingLink, setMeetingLink] = useState('');

  // Form states for Reschedule
  const [newStartTime, setNewStartTime] = useState('');
  const [newEndTime, setNewEndTime] = useState('');

  // Form states for Zoom / Teams link generation
  const [videoTopic, setVideoTopic] = useState('');
  const [generatedLinkResult, setGeneratedLinkResult] = useState<string | null>(null);

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
  const { data: meetings = [], isLoading, refetch } = useMeetingsQuery({
    page,
    limit,
    search: debouncedSearchTerm || undefined,
  });

  useUpcomingMeetingsQuery();

  // Mutations
  const createMeetingMutation = useCreateMeetingMutation();
  const cancelMeetingMutation = useCancelMeetingMutation();
  const bulkCancelMutation = useBulkCancelMeetingsMutation();
  const createZoomMutation = useCreateZoomLinkMutation();
  const createTeamsMutation = useCreateTeamsLinkMutation();
  const rescheduleMutation = useRescheduleMeetingMutation();

  const resetCreateForm = () => {
    setTitle('');
    setStartTime('');
    setEndTime('');
    setAttendeesInput('');
    setMeetingLink('');
  };

  const handleCreateMeetingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setErrorMessage('Meeting title is required.');
      return;
    }

    const attendees = attendeesInput
      .split(',')
      .map((a) => a.trim())
      .filter((a) => a.length > 0);

    const payload: MeetingCreatePayload = {
      title: title.trim(),
      start_time: startTime || new Date().toISOString(),
      end_time: endTime || new Date(Date.now() + 3600000).toISOString(),
      attendee_emails: attendees,
      meeting_link: meetingLink.trim() || undefined,
    };

    try {
      await createMeetingMutation.mutateAsync(payload);
      setSuccessMessage(`Meeting "${title}" scheduled successfully.`);
      setIsCreateModalOpen(false);
      resetCreateForm();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to schedule meeting.'));
    }
  };

  const handleDeleteMeeting = async () => {
    if (!meetingToDelete) return;
    try {
      await cancelMeetingMutation.mutateAsync(meetingToDelete.id);
      setSuccessMessage(`Meeting cancelled successfully.`);
      setMeetingToDelete(null);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to cancel meeting.'));
    }
  };

  const handleBulkCancel = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkCancelMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} meeting(s) cancelled.`);
      setSelectedIds(new Set());
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to cancel selected meetings.'));
    }
  };

  const handleGenerateZoomSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await createZoomMutation.mutateAsync({ topic: videoTopic.trim() || 'Sales Meeting' });
      setGeneratedLinkResult(res.join_url);
      setSuccessMessage(`Zoom meeting link generated: ${res.join_url}`);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to generate Zoom link.'));
    }
  };

  const handleGenerateTeamsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await createTeamsMutation.mutateAsync({ subject: videoTopic.trim() || 'Sales Meeting' });
      setGeneratedLinkResult(res.join_url);
      setSuccessMessage(`Teams meeting link generated: ${res.join_url}`);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to generate Teams link.'));
    }
  };

  const handleRescheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rescheduleMeeting || !newStartTime) return;
    try {
      await rescheduleMutation.mutateAsync({
        meetingId: rescheduleMeeting.id,
        new_start_time: newStartTime,
        new_end_time: newEndTime || newStartTime,
      });
      setSuccessMessage(`Meeting rescheduled successfully.`);
      setRescheduleMeeting(null);
      refetch();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to reschedule meeting.'));
    }
  };

  const handleExportIcal = async () => {
    try {
      const res = await exportIcalFeedApi();
      if (res.ical_url) {
        window.open(res.ical_url, '_blank');
      }
      setSuccessMessage('iCal feed exported successfully.');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to export iCal feed.'));
    }
  };

  // Columns definition
  const columns: DataTableColumn<MeetingItem>[] = [
    {
      id: 'title',
      header: 'MEETING TITLE',
      cell: (item) => (
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-bold shrink-0">
            <Video className="w-4 h-4" />
          </div>
          <div>
            <div
              onClick={(e) => {
                e.stopPropagation();
                router.push(`/meetings/${item.id}`);
              }}
              className="font-bold text-slate-900 hover:text-indigo-600 cursor-pointer transition-colors"
            >
              {item.title}
            </div>
            {item.meeting_link && (
              <a
                href={item.meeting_link}
                target="_blank"
                rel="noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-xs text-indigo-600 hover:underline flex items-center gap-1 mt-0.5"
              >
                <ExternalLink className="w-3 h-3" />
                Join Room
              </a>
            )}
          </div>
        </div>
      ),
    },
    {
      id: 'start_time',
      header: 'START TIME',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-semibold">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.start_time ? item.start_time.replace('T', ' ').substring(0, 16) : 'Scheduled'}</span>
        </div>
      ),
    },
    {
      id: 'end_time',
      header: 'END TIME',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Calendar className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.end_time ? item.end_time.replace('T', ' ').substring(0, 16) : 'Duration 1 hr'}</span>
        </div>
      ),
    },
    {
      id: 'attendees',
      header: 'ATTENDEES',
      cell: (item) => (
        <div className="flex items-center gap-1 text-xs font-medium text-slate-600">
          <Users className="w-3.5 h-3.5 text-slate-400 mr-1" />
          {item.attendees && item.attendees.length > 0 ? (
            <span className="px-2 py-0.5 bg-slate-100 border border-slate-200 rounded-md font-semibold text-slate-800">
              {item.attendees.length} Attendee(s)
            </span>
          ) : (
            <span className="text-slate-400">Team</span>
          )}
        </div>
      ),
    },
    {
      id: 'ai_summary',
      header: 'AI SUMMARY',
      cell: (item) => (
        <div>
          {item.ai_summary ? (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
              <Sparkles className="w-3 h-3 text-indigo-600" />
              Generated
            </span>
          ) : (
            <span className="text-xs text-slate-400 font-medium">Pending</span>
          )}
        </div>
      ),
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (item) => (
        <ActionMenu
          iconOnly
          label="Open meeting actions"
          onTriggerClick={(event) => event.stopPropagation()}
          actions={[
            { label: 'View details & transcript', icon: <FileText className="w-4 h-4 text-indigo-600" />, onSelect: () => router.push(`/meetings/${item.id}`) },
            { label: 'Reschedule meeting', icon: <Clock className="w-4 h-4 text-amber-500" />, onSelect: () => { setRescheduleMeeting(item); setNewStartTime(item.start_time ? item.start_time.substring(0, 16) : ''); } },
            { label: 'Cancel meeting', icon: <Trash2 className="w-4 h-4" />, variant: 'destructive', onSelect: () => setMeetingToDelete(item) },
          ]}
        />
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
            <Video className="w-7 h-7 text-indigo-600" />
            Meetings & AI Summaries
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Schedule meetings with Zoom/Teams integration & AI transcript summaries</p>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <PermissionGate permission={PERMISSIONS.MEETINGS.CREATE}>
            <Button onClick={() => { resetCreateForm(); setIsCreateModalOpen(true); }} className="w-full gap-2 text-xs font-semibold sm:w-auto">
              <Plus className="w-4 h-4" />Schedule Meeting
            </Button>
          </PermissionGate>
          <ActionMenu label="More" className="w-full text-xs font-semibold sm:w-auto" actions={[
            { label: 'Create Zoom link', icon: <Video className="w-4 h-4 text-blue-600" />, onSelect: () => setIsZoomModalOpen(true) },
            { label: 'Create Teams link', icon: <Share2 className="w-4 h-4 text-indigo-600" />, onSelect: () => setIsTeamsModalOpen(true) },
            { label: 'Export iCal', icon: <Download className="w-4 h-4 text-slate-500" />, onSelect: handleExportIcal },
          ]} />
        </div>
      </div>



      {/* Main Data Table */}
      <DataTable<MeetingItem>
        columns={columns}
        data={meetings}
        getRowKey={(item) => item.id}
        onRowClick={(item) => router.push(`/meetings/${item.id}`)}
        emptyTitle="No scheduled meetings found"
        emptyDescription="Schedule a new meeting or generate Zoom/Teams room links."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search meeting title..."
        toolbarActions={
          selectedIds.size > 0 ? (
            <div className="flex w-full flex-wrap items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1 sm:w-auto">
              <span className="text-xs font-semibold text-indigo-700">{selectedIds.size} selected</span>
              <button
                onClick={handleBulkCancel}
                className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold cursor-pointer"
              >
                Bulk Cancel
              </button>
            </div>
          ) : undefined
        }
        isLoading={isLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: meetings.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + meetings.length,
        }}
      />

      {/* Schedule Meeting Modal */}
      <ModalShell
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        size="lg"
        title={
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Video className="w-5 h-5 text-indigo-600" />
            Schedule New Meeting
          </h2>
        }
      >
        <form onSubmit={handleCreateMeetingSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Meeting Title *
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Q3 Sales Review with Client"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                Start Time
              </label>
              <input
                type="datetime-local"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                End Time
              </label>
              <input
                type="datetime-local"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Attendees (comma-separated emails)
            </label>
            <input
              type="text"
              value={attendeesInput}
              onChange={(e) => setAttendeesInput(e.target.value)}
              placeholder="john@example.com, sara@example.com"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Meeting URL Link
            </label>
            <input
              type="url"
              value={meetingLink}
              onChange={(e) => setMeetingLink(e.target.value)}
              placeholder="https://zoom.us/j/123456789 or https://meet.google.com/..."
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-3 border-t border-slate-100">
            <button type="button" onClick={() => setIsCreateModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600">
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMeetingMutation.isPending}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
            >
              {createMeetingMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
              Schedule Meeting
            </button>
          </div>
        </form>
      </ModalShell>

      {/* Generate Zoom Link Modal */}
      <ModalShell
        isOpen={isZoomModalOpen}
        onClose={() => setIsZoomModalOpen(false)}
        size="md"
        title={
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Video className="w-5 h-5 text-blue-600" />
            Generate Zoom Meeting URL
          </h3>
        }
      >
        <form onSubmit={handleGenerateZoomSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Meeting Topic</label>
            <input
              type="text"
              value={videoTopic}
              onChange={(e) => setVideoTopic(e.target.value)}
              placeholder="e.g. Technical Product Demo"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {generatedLinkResult && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-900 space-y-1">
              <span className="font-bold block">Generated Zoom Join URL:</span>
              <a href={generatedLinkResult} target="_blank" rel="noreferrer" className="underline font-mono break-all">
                {generatedLinkResult}
              </a>
            </div>
          )}

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
            <button type="button" onClick={() => setIsZoomModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
              Close
            </button>
            <button
              type="submit"
              disabled={createZoomMutation.isPending}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
            >
              {createZoomMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Generate Link
            </button>
          </div>
        </form>
      </ModalShell>

      {/* Generate Teams Link Modal */}
      <ModalShell
        isOpen={isTeamsModalOpen}
        onClose={() => setIsTeamsModalOpen(false)}
        size="md"
        title={
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Share2 className="w-5 h-5 text-indigo-600" />
            Generate MS Teams Meeting URL
          </h3>
        }
      >
        <form onSubmit={handleGenerateTeamsSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Meeting Subject</label>
            <input
              type="text"
              value={videoTopic}
              onChange={(e) => setVideoTopic(e.target.value)}
              placeholder="e.g. Contract Discussion"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {generatedLinkResult && (
            <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-lg text-xs text-indigo-900 space-y-1">
              <span className="font-bold block">Generated Teams Join URL:</span>
              <a href={generatedLinkResult} target="_blank" rel="noreferrer" className="underline font-mono break-all">
                {generatedLinkResult}
              </a>
            </div>
          )}

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
            <button type="button" onClick={() => setIsTeamsModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
              Close
            </button>
            <button
              type="submit"
              disabled={createTeamsMutation.isPending}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
            >
              {createTeamsMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Generate Link
            </button>
          </div>
        </form>
      </ModalShell>

      {/* Reschedule Modal */}
      <ModalShell
        isOpen={!!rescheduleMeeting}
        onClose={() => setRescheduleMeeting(null)}
        size="md"
        title={
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Clock className="w-5 h-5 text-indigo-600" />
            Reschedule Meeting
          </h3>
        }
      >
        <form onSubmit={handleRescheduleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">New Start Time</label>
            <input
              type="datetime-local"
              required
              value={newStartTime}
              onChange={(e) => setNewStartTime(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">New End Time</label>
            <input
              type="datetime-local"
              value={newEndTime}
              onChange={(e) => setNewEndTime(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
            <button type="button" onClick={() => setRescheduleMeeting(null)} className="px-4 py-2 text-xs font-semibold text-slate-600">
              Cancel
            </button>
            <button
              type="submit"
              disabled={rescheduleMutation.isPending}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
            >
              {rescheduleMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Confirm Reschedule
            </button>
          </div>
        </form>
      </ModalShell>

      {/* Confirm Delete Modal */}
      {meetingToDelete && (
        <ConfirmModal
          isOpen={!!meetingToDelete}
          title="Cancel Meeting"
          description={`Are you sure you want to cancel "${meetingToDelete.title}"?`}
          confirmText="Cancel Meeting"
          variant="danger"
          onConfirm={handleDeleteMeeting}
          onClose={() => setMeetingToDelete(null)}
        />
      )}
    </div>
  );
}
