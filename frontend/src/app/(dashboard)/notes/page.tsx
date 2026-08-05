'use client';

import React, { useState, useEffect } from 'react';
import {
  FileText,
  Pin,
  PinOff,
  Plus,
  Search,
  Trash2,
  Edit,
  Building,
  User,
  DollarSign,
  Layers,
  Sparkles,
  Loader2,
  X,
  CheckCircle2,
  AlertCircle,
  Clock,
  Star
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { ConfirmModal } from '@/components/shared/confirm-modal';
import {
  useNotesQuery,
  usePinnedNotesQuery,
  useCreateNoteMutation,
  useUpdateNoteMutation,
  useDeleteNoteMutation,
  useBulkDeleteNotesMutation,
  usePinNoteMutation,
  useUnpinNoteMutation,
  NoteItem,
  NoteCreatePayload
} from '@/lib/api/notes';

export default function NotesPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [entityTypeFilter, setEntityTypeFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const limit = 15;

  // Selected notes for bulk deletion
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Modal states
  const [isNoteModalOpen, setIsNoteModalOpen] = useState(false);
  const [editingNote, setEditingNote] = useState<NoteItem | null>(null);
  const [noteToDelete, setNoteToDelete] = useState<NoteItem | null>(null);

  // Form states
  const [entityType, setEntityType] = useState('Lead');
  const [entityId, setEntityId] = useState('entity-101');
  const [content, setContent] = useState('');

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
  const { data: notes = [], isLoading: isNotesLoading } = useNotesQuery({
    page,
    limit,
    entity_type: entityTypeFilter || undefined,
    search: debouncedSearchTerm || undefined,
  });

  const { data: pinnedNotes = [] } = usePinnedNotesQuery();

  // Mutations
  const createNoteMutation = useCreateNoteMutation();
  const updateNoteMutation = useUpdateNoteMutation();
  const deleteNoteMutation = useDeleteNoteMutation();
  const bulkDeleteMutation = useBulkDeleteNotesMutation();
  const pinNoteMutation = usePinNoteMutation();
  const unpinNoteMutation = useUnpinNoteMutation();

  const resetForm = () => {
    setEntityType('Lead');
    setEntityId('entity-101');
    setContent('');
    setEditingNote(null);
  };

  const handleOpenCreateModal = () => {
    resetForm();
    setIsNoteModalOpen(true);
  };

  const handleOpenEditModal = (n: NoteItem) => {
    setEditingNote(n);
    setEntityType(n.entity_type || 'Lead');
    setEntityId(n.entity_id || 'entity-101');
    setContent(n.content || '');
    setIsNoteModalOpen(true);
  };

  const handleSaveNoteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) {
      setErrorMessage('Note content cannot be empty.');
      return;
    }

    try {
      if (editingNote) {
        await updateNoteMutation.mutateAsync({ id: editingNote.id, content: content.trim() });
        setSuccessMessage('Note content updated.');
      } else {
        const payload: NoteCreatePayload = {
          entity_type: entityType,
          entity_id: entityId.trim() || 'entity-101',
          content: content.trim(),
        };
        await createNoteMutation.mutateAsync(payload);
        setSuccessMessage('New note created successfully.');
      }
      setIsNoteModalOpen(false);
      resetForm();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to save note.');
    }
  };

  const handleDeleteNote = async () => {
    if (!noteToDelete) return;
    try {
      await deleteNoteMutation.mutateAsync(noteToDelete.id);
      setSuccessMessage('Note deleted successfully.');
      setNoteToDelete(null);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete note.');
    }
  };

  const handleTogglePin = async (n: NoteItem) => {
    try {
      if (n.is_pinned) {
        await unpinNoteMutation.mutateAsync(n.id);
        setSuccessMessage('Note unpinned.');
      } else {
        await pinNoteMutation.mutateAsync(n.id);
        setSuccessMessage('Note pinned to top of timeline.');
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to update pin state.');
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} note(s) deleted.`);
      setSelectedIds(new Set());
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete selected notes.');
    }
  };

  // Columns definition
  const columns: DataTableColumn<NoteItem>[] = [
    {
      id: 'entity_type',
      header: 'ENTITY LINKED',
      cell: (item) => {
        const type = item.entity_type || 'General';
        const style =
          type === 'Lead'
            ? 'bg-blue-50 text-blue-700 border-blue-200'
            : type === 'Contact'
            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
            : type === 'Deal'
            ? 'bg-amber-50 text-amber-700 border-amber-200'
            : 'bg-purple-50 text-purple-700 border-purple-200';
        return (
          <div>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${style}`}>
              {type}
            </span>
            <div className="text-[11px] text-slate-400 font-mono mt-1">ID: {item.entity_id}</div>
          </div>
        );
      },
    },
    {
      id: 'content',
      header: 'NOTE CONTENT',
      cell: (item) => (
        <div className="flex items-start gap-2 max-w-md">
          {item.is_pinned && <Pin className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5 fill-amber-500" />}
          <p className="text-xs text-slate-800 font-medium leading-relaxed truncate">{item.content}</p>
        </div>
      ),
    },
    {
      id: 'created_by',
      header: 'AUTHOR',
      cell: (item) => (
        <div className="text-xs text-slate-700 font-semibold">{item.created_by || 'Sales Rep'}</div>
      ),
    },
    {
      id: 'created_at',
      header: 'CREATED AT',
      cell: (item) => (
        <div className="text-xs text-slate-500 font-medium">
          {item.created_at ? item.created_at.replace('T', ' ').substring(0, 16) : 'Just now'}
        </div>
      ),
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (item) => (
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => handleTogglePin(item)}
            title={item.is_pinned ? 'Unpin Note' : 'Pin Note'}
            className={`p-1.5 rounded-md transition-colors cursor-pointer ${
              item.is_pinned ? 'text-amber-600 hover:bg-amber-50' : 'text-slate-400 hover:text-amber-500 hover:bg-slate-100'
            }`}
          >
            {item.is_pinned ? <PinOff className="w-4 h-4" /> : <Pin className="w-4 h-4" />}
          </button>
          <button
            onClick={() => handleOpenEditModal(item)}
            title="Edit Note"
            className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-slate-100 rounded-md transition-colors cursor-pointer"
          >
            <Edit className="w-4 h-4" />
          </button>
          <button
            onClick={() => setNoteToDelete(item)}
            title="Delete Note"
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
            <FileText className="w-7 h-7 text-indigo-600" />
            Notes & Entity Timeline
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Internal timeline notes linked across leads, contacts, deals, and accounts</p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <select
            value={entityTypeFilter}
            onChange={(e) => setEntityTypeFilter(e.target.value)}
            className="bg-white border border-slate-300 rounded-lg px-3 py-2 text-xs font-semibold text-slate-700 outline-none shadow-xs"
          >
            <option value="">All Entity Types</option>
            <option value="Lead">Leads</option>
            <option value="Contact">Contacts</option>
            <option value="Deal">Deals</option>
            <option value="Company">Companies</option>
          </select>

          <button
            onClick={handleOpenCreateModal}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition-colors shadow-sm cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            Add Note
          </button>
        </div>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">TOTAL NOTES</p>
            <h3 className="text-2xl font-bold text-slate-900 mt-1">{notes.length}</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
            <FileText className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">PINNED NOTES</p>
            <h3 className="text-2xl font-bold text-amber-600 mt-1">{pinnedNotes.length}</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600">
            <Pin className="w-5 h-5 fill-amber-500" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">LINKED ENTITIES</p>
            <h3 className="text-2xl font-bold text-blue-600 mt-1">4 Types</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600">
            <Layers className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">RECENT LOGS</p>
            <h3 className="text-2xl font-bold text-emerald-600 mt-1">Active</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600">
            <Clock className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Pinned Notes Highlight Section */}
      {pinnedNotes.length > 0 && (
        <div className="bg-amber-50/60 rounded-2xl border border-amber-200 p-5 shadow-xs space-y-3">
          <h3 className="text-xs font-bold text-amber-900 uppercase tracking-wider flex items-center gap-2">
            <Pin className="w-4 h-4 text-amber-600 fill-amber-600" />
            Pinned Notes ({pinnedNotes.length})
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {pinnedNotes.map((p) => (
              <div key={p.id} className="p-3.5 bg-white rounded-xl border border-amber-200 shadow-2xs space-y-2">
                <div className="flex justify-between items-center text-[11px] font-bold text-slate-500">
                  <span className="px-2 py-0.5 bg-amber-100 text-amber-800 rounded font-mono">{p.entity_type}</span>
                  <button onClick={() => handleTogglePin(p)} className="text-amber-600 hover:text-amber-800 cursor-pointer">
                    <PinOff className="w-3.5 h-3.5" />
                  </button>
                </div>
                <p className="text-xs text-slate-800 font-medium line-clamp-2">{p.content}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Notes Data Table */}
      <DataTable<NoteItem>
        columns={columns}
        data={notes}
        getRowKey={(item) => item.id}
        emptyTitle="No notes recorded"
        emptyDescription="Add internal notes linked to leads, contacts, deals, or companies."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search notes content..."
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
        isLoading={isNotesLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: notes.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + notes.length,
        }}
      />

      {/* Create / Edit Note Modal */}
      {isNoteModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-5">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-600" />
                {editingNote ? 'Edit Note' : 'Add Note to Entity'}
              </h2>
              <button onClick={() => setIsNoteModalOpen(false)} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveNoteSubmit} className="space-y-4">
              {!editingNote && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                      Entity Type
                    </label>
                    <select
                      value={entityType}
                      onChange={(e) => setEntityType(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                    >
                      <option value="Lead">Lead</option>
                      <option value="Contact">Contact</option>
                      <option value="Deal">Deal</option>
                      <option value="Company">Company</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                      Entity ID / Reference
                    </label>
                    <input
                      type="text"
                      value={entityId}
                      onChange={(e) => setEntityId(e.target.value)}
                      placeholder="e.g. lead-101"
                      className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Note Content *
                </label>
                <textarea
                  rows={5}
                  required
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Record internal call notes, deal updates, or action items..."
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none resize-none font-sans"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button type="button" onClick={() => setIsNoteModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createNoteMutation.isPending || updateNoteMutation.isPending}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
                >
                  {(createNoteMutation.isPending || updateNoteMutation.isPending) && (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  )}
                  {editingNote ? 'Save Changes' : 'Create Note'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirm Delete Modal */}
      {noteToDelete && (
        <ConfirmModal
          isOpen={!!noteToDelete}
          title="Delete Note"
          description={`Are you sure you want to delete this note?`}
          confirmText="Delete Note"
          variant="danger"
          onConfirm={handleDeleteNote}
          onClose={() => setNoteToDelete(null)}
        />
      )}
    </div>
  );
}
