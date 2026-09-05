'use client';

import { Input } from "@/components/ui/input";

import { ResponsiveSelect } from '@/components/common/responsive-select';
import { DateTimePicker } from '@/components/common/date-picker';
import { Textarea } from '@/components/ui/textarea';

import { getErrorMessage } from '@/lib/utils';
import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Video,
  Calendar,
  Clock,
  ExternalLink,
  Users,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Trash2,
  Edit,
  Upload,
  UserCheck,
  ListTodo
} from 'lucide-react';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import {
  useMeetingQuery,
  useMeetingAiSummaryQuery,
  useMeetingActionItemsQuery,
  useUpdateMeetingMutation,
  useCancelMeetingMutation,
  useRescheduleMeetingMutation,
  useMeetingRsvpMutation,
  useUploadTranscriptMutation,
  MeetingUpdatePayload
} from '@/lib/api/meetings';

export default function MeetingDetailPage() {
  const params = useParams();
  const router = useRouter();
  const meetingId = (params?.id as string) || '';

  // Queries
  const { data: meeting, isLoading, isError, refetch } = useMeetingQuery(meetingId);
  const { data: aiSummaryData, refetch: refetchAiSummary } = useMeetingAiSummaryQuery(meetingId);
  const { data: actionItems = [] } = useMeetingActionItemsQuery(meetingId);

  // Mutations
  const updateMutation = useUpdateMeetingMutation();
  const cancelMutation = useCancelMeetingMutation();
  const rescheduleMutation = useRescheduleMeetingMutation();
  const rsvpMutation = useMeetingRsvpMutation();
  const uploadTranscriptMutation = useUploadTranscriptMutation();

  // State
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isRescheduleModalOpen, setIsRescheduleModalOpen] = useState(false);

  // Form states
  const [title, setTitle] = useState('');
  const [meetingLink, setMeetingLink] = useState('');
  const [newStartTime, setNewStartTime] = useState('');
  const [newEndTime, setNewEndTime] = useState('');
  const [rsvpEmail, setRsvpEmail] = useState('');
  const [rsvpStatus, setRsvpStatus] = useState('Accepted');
  const [transcriptText, setTranscriptText] = useState('');

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleOpenEditModal = () => {
    if (!meeting) return;
    setTitle(meeting.title || '');
    setMeetingLink(meeting.meeting_link || '');
    setIsEditModalOpen(true);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    const payload: MeetingUpdatePayload = {
      title: title.trim(),
      meeting_link: meetingLink.trim() || undefined,
    };

    try {
      await updateMutation.mutateAsync({ id: meetingId, payload });
      setSuccessMessage('Meeting details updated successfully.');
      setIsEditModalOpen(false);
      refetch();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to update meeting.'));
    }
  };

  const handleDeleteMeeting = async () => {
    try {
      await cancelMutation.mutateAsync(meetingId);
      router.push('/meetings');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to cancel meeting.'));
    }
  };

  const handleRescheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStartTime) return;
    try {
      await rescheduleMutation.mutateAsync({
        meetingId,
        new_start_time: newStartTime,
        new_end_time: newEndTime || newStartTime,
      });
      setSuccessMessage('Meeting rescheduled successfully.');
      setIsRescheduleModalOpen(false);
      refetch();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to reschedule meeting.'));
    }
  };

  const handleRsvpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rsvpEmail.trim()) return;
    try {
      await rsvpMutation.mutateAsync({
        meetingId,
        email: rsvpEmail.trim(),
        response: rsvpStatus,
      });
      setSuccessMessage(`RSVP "${rsvpStatus}" recorded for ${rsvpEmail}.`);
      setRsvpEmail('');
      refetch();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to record RSVP.'));
    }
  };

  const handleTranscriptSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!transcriptText.trim()) return;
    try {
      await uploadTranscriptMutation.mutateAsync({
        meetingId,
        transcript_text: transcriptText.trim(),
      });
      setSuccessMessage('Transcript uploaded and AI summary generated.');
      setTranscriptText('');
      refetchAiSummary();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to upload transcript.'));
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-2 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          <span className="text-sm font-medium">Loading meeting details...</span>
        </div>
      </div>
    );
  }

  if (isError || !meeting) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-4">
        <Link href="/meetings" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 font-medium">
          <ArrowLeft className="w-4 h-4" />
          Back to Meetings
        </Link>
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 space-y-2">
          <div className="flex items-center gap-2 font-bold text-base">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            Meeting Not Found
          </div>
          <p className="text-sm">The meeting you requested could not be found or may have been cancelled.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Navigation & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Link href="/meetings" className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-indigo-600 transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Back to Meeting List
          </Link>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-3">
            <Video className="w-6 h-6 text-indigo-600" />
            {meeting.title}
          </h1>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {meeting.meeting_link && (
            <a
              href={meeting.meeting_link}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-semibold cursor-pointer shadow-sm transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              Join Video Room
            </a>
          )}

          <button
            onClick={() => {
              setNewStartTime(meeting.start_time ? meeting.start_time.substring(0, 16) : '');
              setIsRescheduleModalOpen(true);
            }}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm cursor-pointer"
          >
            <Clock className="w-4 h-4 text-slate-500" />
            Reschedule
          </button>

          <button
            onClick={handleOpenEditModal}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm cursor-pointer"
          >
            <Edit className="w-4 h-4 text-slate-500" />
            Edit
          </button>

          <button
            onClick={() => setIsDeleteModalOpen(true)}
            className="flex items-center gap-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 px-3.5 py-2 rounded-lg text-sm font-semibold transition-colors cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
            Cancel Meeting
          </button>
        </div>
      </div>

      {/* Toast Feedback */}
      {successMessage && (
        <div className="flex items-center justify-between p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <span>{successMessage}</span>
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

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Overview, AI Summary & Action Items */}
        <div className="lg:col-span-2 space-y-6">
          {/* Overview Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3">
              Meeting Overview
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Start Time</span>
                <div className="flex items-center gap-2 text-slate-900 font-semibold text-sm">
                  <Clock className="w-4 h-4 text-indigo-600" />
                  <span>{meeting.start_time ? meeting.start_time.replace('T', ' ').substring(0, 16) : 'N/A'}</span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">End Time</span>
                <div className="flex items-center gap-2 text-slate-900 font-semibold text-sm">
                  <Calendar className="w-4 h-4 text-indigo-600" />
                  <span>{meeting.end_time ? meeting.end_time.replace('T', ' ').substring(0, 16) : 'N/A'}</span>
                </div>
              </div>
            </div>

            {meeting.meeting_link && (
              <div className="pt-2 border-t border-slate-100">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1">Meeting Room Link</span>
                <a
                  href={meeting.meeting_link}
                  target="_blank"
                  rel="noreferrer"
                  className="text-indigo-600 hover:underline font-mono text-xs font-semibold break-all"
                >
                  {meeting.meeting_link}
                </a>
              </div>
            )}
          </div>

          {/* AI Summary Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              AI Generated Summary
            </h3>

            <div className="p-4 bg-indigo-50/50 border border-indigo-100 rounded-xl space-y-3">
              <p className="text-sm text-slate-800 leading-relaxed font-medium">
                {aiSummaryData?.summary || meeting.ai_summary || 'No AI summary generated yet. Upload a meeting transcript to generate AI notes.'}
              </p>

              {aiSummaryData?.key_decisions && aiSummaryData.key_decisions.length > 0 && (
                <div className="pt-2 border-t border-indigo-100 space-y-1">
                  <span className="text-xs font-bold text-indigo-900 uppercase tracking-wider">Key Decisions:</span>
                  <ul className="list-disc list-inside text-xs text-indigo-950 space-y-1 font-medium">
                    {aiSummaryData.key_decisions.map((kd, idx) => (
                      <li key={idx}>{kd}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* Action Items Extracted */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <ListTodo className="w-4 h-4 text-indigo-600" />
              AI Extracted Action Items ({actionItems.length})
            </h3>

            <div className="space-y-2">
              {actionItems.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No action items extracted yet.</p>
              ) : (
                actionItems.map((act) => (
                  <div key={act.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <span className="font-semibold text-slate-900">{act.task}</span>
                    </div>
                    <div className="flex items-center gap-2 text-slate-500">
                      <span className="px-2 py-0.5 bg-slate-200 rounded text-[11px] font-semibold">{act.assignee || act.status}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Attendees, RSVP & Transcript Upload */}
        <div className="space-y-6">
          {/* Attendees List */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <Users className="w-4 h-4 text-indigo-600" />
              Meeting Attendees
            </h3>

            <div className="space-y-2">
              {meeting.attendees && meeting.attendees.length > 0 ? (
                meeting.attendees.map((att, idx) => (
                  <div key={idx} className="flex items-center gap-2 p-2.5 bg-slate-50 rounded-xl border border-slate-200 text-xs font-semibold text-slate-800">
                    <UserCheck className="w-4 h-4 text-emerald-600" />
                    <span>{att}</span>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-400 italic">No external attendees specified.</p>
              )}
            </div>

            {/* RSVP Form */}
            <form onSubmit={handleRsvpSubmit} className="space-y-2 pt-3 border-t border-slate-100">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">Update RSVP</label>
              <Input
                type="email"
                required
                value={rsvpEmail}
                onChange={(e) => setRsvpEmail(e.target.value)}
                placeholder="Attendee Email..."
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <ResponsiveSelect
                value={rsvpStatus}
                onValueChange={setRsvpStatus}
                className="w-full bg-slate-50 border border-slate-300 text-xs rounded-lg px-3 py-1.5 outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="Accepted">Accepted</option>
                <option value="Declined">Declined</option>
                <option value="Tentative">Tentative</option>
              </ResponsiveSelect>
              <button
                type="submit"
                disabled={rsvpMutation.isPending}
                className="w-full bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold py-2 rounded-lg cursor-pointer"
              >
                Record RSVP Status
              </button>
            </form>
          </div>

          {/* Upload Transcript Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <Upload className="w-4 h-4 text-indigo-600" />
              Upload Transcript
            </h3>

            <form onSubmit={handleTranscriptSubmit} className="space-y-3">
              <Textarea
                rows={4}
                value={transcriptText}
                onChange={(e) => setTranscriptText(e.target.value)}
                placeholder="Paste meeting transcript notes or dialogue here to analyze..."
                className="w-full bg-slate-50 border border-slate-300 rounded-xl p-3 text-xs text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none resize-none"
              />
              <button
                type="submit"
                disabled={!transcriptText.trim() || uploadTranscriptMutation.isPending}
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold py-2 rounded-lg cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {uploadTranscriptMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <Sparkles className="w-3.5 h-3.5" />
                Process & Summarize AI
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Edit Modal */}
      {isEditModalOpen && (
        <ModalShell
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          size="md"
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Video className="w-5 h-5 text-indigo-600" />
              Edit Meeting Details
            </h3>
          }
        >
          <form onSubmit={handleSaveEdit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Meeting Title *</label>
              <Input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Meeting Room URL</label>
              <Input
                type="url"
                value={meetingLink}
                onChange={(e) => setMeetingLink(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-2">
              <button type="button" onClick={() => setIsEditModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={updateMutation.isPending}
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {updateMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Save Changes
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Reschedule Modal */}
      {isRescheduleModalOpen && (
        <ModalShell
          isOpen={isRescheduleModalOpen}
          onClose={() => setIsRescheduleModalOpen(false)}
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
              <label htmlFor="meeting-reschedule-start" className="block text-xs font-semibold text-slate-700 mb-1">New Start Time</label>
              <DateTimePicker
                id="meeting-reschedule-start"
                required
                value={newStartTime}
                onValueChange={setNewStartTime}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label htmlFor="meeting-reschedule-end" className="block text-xs font-semibold text-slate-700 mb-1">New End Time</label>
              <DateTimePicker
                id="meeting-reschedule-end"
                value={newEndTime}
                onValueChange={setNewEndTime}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-2">
              <button type="button" onClick={() => setIsRescheduleModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
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
      )}

      {/* Delete Confirm Modal */}
      {isDeleteModalOpen && (
        <ConfirmModal
          isOpen={isDeleteModalOpen}
          title="Cancel Meeting"
          description={`Are you sure you want to cancel "${meeting.title}"?`}
          confirmText="Cancel Meeting"
          variant="danger"
          onConfirm={handleDeleteMeeting}
          onClose={() => setIsDeleteModalOpen(false)}
        />
      )}
    </div>
  );
}
