'use client';

import { getErrorMessage } from '@/lib/utils';
import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  PhoneCall,
  PhoneOutgoing,
  PhoneIncoming,
  Clock,
  Volume2,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Trash2,
} from 'lucide-react';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { useHasPermission } from '@/hooks/use-has-permission';
import { PERMISSIONS } from '@/lib/permissions';
import {
  useCallQuery,
  useCallRecordingQuery,
  useCallSentimentQuery,
  useDeleteCallMutation
} from '@/lib/api/calls';

export default function CallDetailPage() {
  const params = useParams();
  const router = useRouter();
  const callId = (params?.id as string) || '';
  const { hasPermission } = useHasPermission();
  const canAnalyzeSentiment = hasPermission(PERMISSIONS.AI.GENERATE)
    && hasPermission(PERMISSIONS.CALLS.READ);

  // Queries
  const { data: call, isLoading, isError } = useCallQuery(callId);
  const { data: recording } = useCallRecordingQuery(callId);
  const {
    data: sentiment,
    isLoading: isSentimentLoading,
    isError: isSentimentError,
  } = useCallSentimentQuery(callId, { enabled: Boolean(callId) && canAnalyzeSentiment });

  // Mutations
  const deleteMutation = useDeleteCallMutation();

  // State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleDeleteCall = async () => {
    try {
      await deleteMutation.mutateAsync(callId);
      router.push('/calls');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete call log.'));
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '0m 0s';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-2 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          <span className="text-sm font-medium">Loading call details...</span>
        </div>
      </div>
    );
  }

  if (isError || !call) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-4">
        <Link href="/calls" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 font-medium">
          <ArrowLeft className="w-4 h-4" />
          Back to Call Logs
        </Link>
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 space-y-2">
          <div className="flex items-center gap-2 font-bold text-base">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            Call Log Not Found
          </div>
          <p className="text-sm">The call log you requested could not be found or may have been deleted.</p>
        </div>
      </div>
    );
  }

  const isOutbound = call.call_type !== 'Inbound';

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Navigation & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Link href="/calls" className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-indigo-600 transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Back to Call Logs
          </Link>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-3">
            <PhoneCall className="w-6 h-6 text-indigo-600" />
            Call Log: {call.contact_id || 'Client Contact'}
          </h1>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => setIsDeleteModalOpen(true)}
            className="flex items-center gap-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 px-3.5 py-2 rounded-lg text-sm font-semibold transition-colors cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
            Delete Log
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
        {/* Left Column: Overview, Audio Recording Player & Call Notes */}
        <div className="lg:col-span-2 space-y-6">
          {/* Overview Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3">
              Call Overview
            </h3>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Direction</span>
                <div className="flex items-center gap-2 font-bold text-sm text-slate-900">
                  {isOutbound ? <PhoneOutgoing className="w-4 h-4 text-indigo-600" /> : <PhoneIncoming className="w-4 h-4 text-emerald-600" />}
                  <span>{call.call_type || 'Outbound'}</span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Duration</span>
                <div className="flex items-center gap-2 text-slate-900 font-semibold text-sm">
                  <Clock className="w-4 h-4 text-slate-400" />
                  <span>{formatDuration(call.duration_seconds)}</span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Timestamp</span>
                <div className="text-slate-900 font-semibold text-sm">
                  {call.timestamp ? call.timestamp.replace('T', ' ').substring(0, 16) : 'Just now'}
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Call Notes</span>
              <p className="text-sm text-slate-700 bg-slate-50 p-4 rounded-xl border border-slate-200 min-h-[90px] leading-relaxed font-medium">
                {call.notes || 'No notes recorded for this call session.'}
              </p>
            </div>
          </div>

          {/* Audio Recording Player */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <Volume2 className="w-4 h-4 text-indigo-600" />
              MinIO S3 Audio Recording
            </h3>

            {recording?.recording_url ? (
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                <span className="text-xs font-semibold text-slate-600 block">Presigned Playback Stream:</span>
                <audio controls className="w-full h-10 rounded-lg">
                  <source src={recording.recording_url} type="audio/mp3" />
                  Your browser does not support playing audio recordings.
                </audio>
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">No audio recording available for this call.</p>
            )}
          </div>
        </div>

        {/* Right Column: AI Voice Sentiment & Emotion Breakdown */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              AI Voice Sentiment
            </h3>

            {!canAnalyzeSentiment ? (
              <p className="text-xs text-slate-500">AI and call read permissions are required.</p>
            ) : isSentimentLoading ? (
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" /> Analyzing recorded call notes…
              </div>
            ) : isSentimentError || !sentiment ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                Sentiment is unavailable. The call must contain notes and the AI provider must be available.
              </div>
            ) : (
            <div className="space-y-4" aria-live="polite">
              <div className="p-4 bg-indigo-50/50 border border-indigo-100 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-indigo-700 block uppercase tracking-wider">Overall Sentiment</span>
                  <h4 className="text-lg font-extrabold text-indigo-950 mt-0.5">
                    {sentiment.overall_sentiment}
                  </h4>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                  <span className="text-slate-400 block font-medium">Confidence</span>
                  <span className="text-sm font-bold text-slate-900 mt-0.5 block">
                    {Math.round(sentiment.confidence_score * 100)}%
                  </span>
                </div>

                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                  <span className="text-slate-400 block font-medium">Urgency</span>
                  <span className="text-sm font-bold text-indigo-600 mt-0.5 block">
                    {sentiment.urgency}
                  </span>
                </div>
              </div>
              <div className="space-y-2 border-t border-slate-100 pt-3 text-xs text-slate-700">
                <p className="font-semibold">
                  Escalation required: {sentiment.escalation_required ? 'Yes' : 'No'}
                </p>
                {sentiment.reasons.length > 0 && (
                  <ul className="list-disc space-y-1 pl-5">
                    {sentiment.reasons.map((reason) => <li key={reason}>{reason}</li>)}
                  </ul>
                )}
              </div>
            </div>
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirm Modal */}
      {isDeleteModalOpen && (
        <ConfirmModal
          isOpen={isDeleteModalOpen}
          title="Delete Call Log"
          description={`Are you sure you want to delete this call log?`}
          confirmText="Delete Call Log"
          variant="danger"
          onConfirm={handleDeleteCall}
          onClose={() => setIsDeleteModalOpen(false)}
        />
      )}
    </div>
  );
}
