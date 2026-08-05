'use client';

import React, { useState, useEffect } from 'react';
import {
  Calendar as CalendarIcon,
  Clock,
  Plus,
  Search,
  RefreshCw,
  Trash2,
  Edit,
  Repeat,
  UserCheck,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Zap,
  Globe,
  CalendarCheck
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { ConfirmModal } from '@/components/shared/confirm-modal';
import {
  useCalendarEventsQuery,
  useAvailabilityQuery,
  useRecurringEventsQuery,
  useCreateCalendarEventMutation,
  useUpdateCalendarEventMutation,
  useDeleteCalendarEventMutation,
  useSyncGoogleCalendarMutation,
  useSyncOutlookCalendarMutation,
  useCreateRecurringEventMutation,
  CalendarEventItem,
  CalendarEventCreatePayload
} from '@/lib/api/calendar';

export default function CalendarPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState<'table' | 'availability' | 'recurring'>('table');

  // Selected event for delete / edit
  const [eventToDelete, setEventToDelete] = useState<CalendarEventItem | null>(null);
  const [editingEvent, setEditingEvent] = useState<CalendarEventItem | null>(null);

  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isRecurringModalOpen, setIsRecurringModalOpen] = useState(false);

  // Event Form state
  const [title, setTitle] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [eventType, setEventType] = useState('Meeting');
  const [description, setDescription] = useState('');

  // Recurring Event Form state
  const [recurringTitle, setRecurringTitle] = useState('');
  const [rrulePattern, setRrulePattern] = useState('FREQ=WEEKLY;BYDAY=MO');

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Debounce search
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Queries
  const { data: events = [], isLoading: isEventsLoading, refetch } = useCalendarEventsQuery({
    search: debouncedSearchTerm || undefined,
  });

  const { data: availability } = useAvailabilityQuery();
  const { data: recurringRules = [] } = useRecurringEventsQuery();

  // Mutations
  const createEventMutation = useCreateCalendarEventMutation();
  const updateEventMutation = useUpdateCalendarEventMutation();
  const deleteEventMutation = useDeleteCalendarEventMutation();
  const syncGoogleMutation = useSyncGoogleCalendarMutation();
  const syncOutlookMutation = useSyncOutlookCalendarMutation();
  const createRecurringMutation = useCreateRecurringEventMutation();

  const resetForm = () => {
    setTitle('');
    setStart('');
    setEnd('');
    setEventType('Meeting');
    setDescription('');
    setEditingEvent(null);
  };

  const handleOpenCreateModal = () => {
    resetForm();
    setIsCreateModalOpen(true);
  };

  const handleOpenEditModal = (evt: CalendarEventItem) => {
    setEditingEvent(evt);
    setTitle(evt.title || '');
    setStart(evt.start ? evt.start.substring(0, 16) : '');
    setEnd(evt.end ? evt.end.substring(0, 16) : '');
    setEventType(evt.event_type || 'Meeting');
    setDescription(evt.description || '');
    setIsCreateModalOpen(true);
  };

  const handleSaveEventSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setErrorMessage('Event title is required.');
      return;
    }

    const payload: CalendarEventCreatePayload = {
      title: title.trim(),
      start: start || new Date().toISOString(),
      end: end || new Date(Date.now() + 3600000).toISOString(),
      event_type: eventType,
      description: description.trim() || undefined,
    };

    try {
      if (editingEvent) {
        await updateEventMutation.mutateAsync({ id: editingEvent.id, payload });
        setSuccessMessage(`Event "${title}" updated.`);
      } else {
        await createEventMutation.mutateAsync(payload);
        setSuccessMessage(`Calendar event "${title}" created successfully.`);
      }
      setIsCreateModalOpen(false);
      resetForm();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to save event.');
    }
  };

  const handleDeleteEvent = async () => {
    if (!eventToDelete) return;
    try {
      await deleteEventMutation.mutateAsync(eventToDelete.id);
      setSuccessMessage('Calendar event deleted.');
      setEventToDelete(null);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete event.');
    }
  };

  const handleSyncGoogle = async () => {
    try {
      const res = await syncGoogleMutation.mutateAsync();
      setSuccessMessage(res.message || 'Google Calendar synchronized.');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to sync Google Calendar.');
    }
  };

  const handleSyncOutlook = async () => {
    try {
      const res = await syncOutlookMutation.mutateAsync();
      setSuccessMessage(res.message || 'Outlook Calendar synchronized.');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to sync Outlook Calendar.');
    }
  };

  const handleCreateRecurringSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recurringTitle.trim()) return;
    try {
      await createRecurringMutation.mutateAsync({
        title: recurringTitle.trim(),
        rrule: rrulePattern,
      });
      setSuccessMessage(`Recurring rule "${recurringTitle.trim()}" created.`);
      setIsRecurringModalOpen(false);
      setRecurringTitle('');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to create recurring rule.');
    }
  };

  // Columns definition
  const columns: DataTableColumn<CalendarEventItem>[] = [
    {
      id: 'title',
      header: 'EVENT TITLE',
      cell: (item) => (
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-bold shrink-0">
            <CalendarIcon className="w-4 h-4" />
          </div>
          <div>
            <div className="font-bold text-slate-900 text-xs">{item.title}</div>
            {item.description && (
              <div className="text-[11px] text-slate-500 truncate max-w-xs">{item.description}</div>
            )}
          </div>
        </div>
      ),
    },
    {
      id: 'event_type',
      header: 'TYPE',
      cell: (item) => {
        const type = item.event_type || 'Meeting';
        const style =
          type === 'Meeting'
            ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
            : type === 'Internal'
            ? 'bg-amber-50 text-amber-700 border-amber-200'
            : 'bg-emerald-50 text-emerald-700 border-emerald-200';
        return (
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${style}`}>
            {type}
          </span>
        );
      },
    },
    {
      id: 'start',
      header: 'START TIME',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-semibold">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.start ? item.start.replace('T', ' ').substring(0, 16) : 'Scheduled'}</span>
        </div>
      ),
    },
    {
      id: 'end',
      header: 'END TIME',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.end ? item.end.replace('T', ' ').substring(0, 16) : 'Scheduled'}</span>
        </div>
      ),
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (item) => (
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleOpenEditModal(item)}
            title="Edit Event"
            className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-slate-100 rounded-md transition-colors cursor-pointer"
          >
            <Edit className="w-4 h-4" />
          </button>
          <button
            onClick={() => setEventToDelete(item)}
            title="Delete Event"
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
            <span>{successMessage}</span>
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
            <CalendarIcon className="w-7 h-7 text-indigo-600" />
            Calendar & Scheduling
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">2-Way Google & Outlook calendar sync, time slot availability, and recurring events</p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={handleSyncGoogle}
            disabled={syncGoogleMutation.isPending}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer disabled:opacity-50"
          >
            {syncGoogleMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Globe className="w-4 h-4 text-blue-600" />}
            Sync Google
          </button>

          <button
            onClick={handleSyncOutlook}
            disabled={syncOutlookMutation.isPending}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer disabled:opacity-50"
          >
            {syncOutlookMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4 text-indigo-600" />}
            Sync Outlook
          </button>

          <button
            onClick={() => setIsRecurringModalOpen(true)}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            <Repeat className="w-4 h-4 text-amber-500" />
            Recurring Rule
          </button>

          <button
            onClick={handleOpenCreateModal}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition-colors shadow-sm cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            Create Event
          </button>
        </div>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">SCHEDULED EVENTS</p>
            <h3 className="text-2xl font-bold text-slate-900 mt-1">{events.length}</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
            <CalendarCheck className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">AVAILABLE SLOTS TODAY</p>
            <h3 className="text-2xl font-bold text-emerald-600 mt-1">
              {availability?.available_slots ? availability.available_slots.length : 4} Slots
            </h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600">
            <Clock className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">RECURRING RULES</p>
            <h3 className="text-2xl font-bold text-amber-600 mt-1">{recurringRules.length}</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600">
            <Repeat className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">CALENDAR SYNC</p>
            <h3 className="text-sm font-extrabold text-indigo-600 mt-1 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              2-Way Active
            </h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
            <Zap className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* View Switcher Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setViewMode('table')}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
            viewMode === 'table' ? 'bg-indigo-600 text-white shadow-xs' : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          Events List ({events.length})
        </button>

        <button
          onClick={() => setViewMode('availability')}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
            viewMode === 'availability' ? 'bg-indigo-600 text-white shadow-xs' : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          User Availability Slots
        </button>

        <button
          onClick={() => setViewMode('recurring')}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
            viewMode === 'recurring' ? 'bg-indigo-600 text-white shadow-xs' : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          Recurring Rules ({recurringRules.length})
        </button>
      </div>

      {/* View Mode Content */}
      {viewMode === 'table' && (
        <DataTable<CalendarEventItem>
          columns={columns}
          data={events}
          getRowKey={(item) => item.id}
          emptyTitle="No calendar events found"
          emptyDescription="Create a new calendar event or trigger Google/Outlook sync."
          searchValue={searchTerm}
          onSearchChange={setSearchTerm}
          searchPlaceholder="Search event title..."
          isLoading={isEventsLoading}
        />
      )}

      {viewMode === 'availability' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
            <Clock className="w-4 h-4 text-emerald-600" />
            Free & Open Booking Slots
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {availability?.available_slots?.map((slot, idx) => (
              <div key={idx} className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-center space-y-1">
                <span className="text-xs font-bold text-emerald-800 block">Open Window #{idx + 1}</span>
                <span className="text-sm font-extrabold text-emerald-950 block">{slot}</span>
                <span className="text-[11px] text-emerald-700 font-semibold block">Available for Instant Booking</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {viewMode === 'recurring' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
            <Repeat className="w-4 h-4 text-amber-500" />
            Active Recurring Event Rules
          </h3>

          <div className="space-y-3">
            {recurringRules.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No recurring rules configured yet.</p>
            ) : (
              recurringRules.map((rule) => (
                <div key={rule.id} className="flex items-center justify-between p-4 bg-slate-50 border border-slate-200 rounded-xl">
                  <div>
                    <h4 className="text-xs font-bold text-slate-900">{rule.title}</h4>
                    <span className="text-[11px] font-mono text-slate-500 block mt-0.5">rrule: {rule.rrule}</span>
                  </div>
                  <span className="px-2.5 py-1 bg-amber-100 text-amber-800 border border-amber-200 rounded-md text-xs font-semibold">
                    {rule.event_type || 'Internal'}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Create / Edit Event Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-5">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <CalendarIcon className="w-5 h-5 text-indigo-600" />
                {editingEvent ? 'Edit Calendar Event' : 'Create New Event'}
              </h2>
              <button onClick={() => setIsCreateModalOpen(false)} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveEventSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Event Title *
                </label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Sales Pipeline Review"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                    Start Time
                  </label>
                  <input
                    type="datetime-local"
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                    End Time
                  </label>
                  <input
                    type="datetime-local"
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Event Type
                </label>
                <select
                  value={eventType}
                  onChange={(e) => setEventType(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                >
                  <option value="Meeting">Meeting</option>
                  <option value="Internal">Internal Sync</option>
                  <option value="Client Demo">Client Demo</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Description
                </label>
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Notes or outcome objectives for the event..."
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none resize-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button type="button" onClick={() => setIsCreateModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createEventMutation.isPending || updateEventMutation.isPending}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
                >
                  {(createEventMutation.isPending || updateEventMutation.isPending) && (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  )}
                  {editingEvent ? 'Save Changes' : 'Create Event'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Recurring Rule Modal */}
      {isRecurringModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Repeat className="w-5 h-5 text-amber-500" />
                Create Recurring Rule
              </h3>
              <button onClick={() => setIsRecurringModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateRecurringSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Event Rule Title *</label>
                <input
                  type="text"
                  required
                  value={recurringTitle}
                  onChange={(e) => setRecurringTitle(e.target.value)}
                  placeholder="e.g. Weekly Monday Demo"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">RRule Pattern</label>
                <input
                  type="text"
                  value={rrulePattern}
                  onChange={(e) => setRrulePattern(e.target.value)}
                  placeholder="FREQ=WEEKLY;BYDAY=MO"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-amber-500 font-mono"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setIsRecurringModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createRecurringMutation.isPending}
                  className="flex items-center gap-2 bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
                >
                  {createRecurringMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Create Rule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirm Delete Event Modal */}
      {eventToDelete && (
        <ConfirmModal
          isOpen={!!eventToDelete}
          title="Delete Event"
          description={`Are you sure you want to delete "${eventToDelete.title}"?`}
          confirmText="Delete Event"
          variant="danger"
          onConfirm={handleDeleteEvent}
          onClose={() => setEventToDelete(null)}
        />
      )}
    </div>
  );
}
