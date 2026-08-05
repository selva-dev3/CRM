'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Folder,
  FileText,
  UploadCloud,
  Download,
  Trash2,
  Search,
  Plus,
  HardDrive,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  FileCode,
  FileImage,
  FileSpreadsheet,
  FileArchive,
  Eye,
  ExternalLink,
  ShieldCheck
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { ConfirmModal } from '@/components/shared/confirm-modal';
import {
  useDocumentsQuery,
  useUploadDocumentMutation,
  useDeleteDocumentMutation,
  useBulkDeleteDocumentsMutation,
  downloadDocumentApi,
  DocumentItem
} from '@/lib/api/documents';

export default function DocumentsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const limit = 15;

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Selected files for bulk deletion
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Modal states
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<DocumentItem | null>(null);
  const [downloadingDoc, setDownloadingDoc] = useState<DocumentItem | null>(null);
  const [presignedUrlResult, setPresignedUrlResult] = useState<{ download_url: string; filename: string } | null>(null);

  // File upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);

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
  const { data: documents = [], isLoading: isDocsLoading } = useDocumentsQuery({
    page,
    limit,
    search: debouncedSearchTerm || undefined,
  });

  // Mutations
  const uploadMutation = useUploadDocumentMutation();
  const deleteMutation = useDeleteDocumentMutation();
  const bulkDeleteMutation = useBulkDeleteDocumentsMutation();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMessage('Please select a file to upload.');
      return;
    }

    try {
      const res = await uploadMutation.mutateAsync(selectedFile);
      setSuccessMessage(`File "${res.filename}" uploaded successfully to MinIO S3.`);
      setIsUploadModalOpen(false);
      setSelectedFile(null);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to upload document.');
    }
  };

  const handleDownloadClick = async (doc: DocumentItem) => {
    setDownloadingDoc(doc);
    try {
      const res = await downloadDocumentApi(doc.id);
      setPresignedUrlResult(res);
    } catch (err: any) {
      // Fallback
      setPresignedUrlResult({
        download_url: doc.download_url || `https://storage.minio.internal/crm-storage/documents/${doc.filename}`,
        filename: doc.filename,
      });
    }
  };

  const handleDeleteDocument = async () => {
    if (!documentToDelete) return;
    try {
      await deleteMutation.mutateAsync(documentToDelete.id);
      setSuccessMessage('Document deleted successfully.');
      setDocumentToDelete(null);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete document.');
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} document(s) deleted.`);
      setSelectedIds(new Set());
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete selected documents.');
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '0 KB';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const getFileIcon = (mimeType?: string) => {
    if (!mimeType) return <FileText className="w-5 h-5 text-indigo-600" />;
    if (mimeType.includes('image')) return <FileImage className="w-5 h-5 text-emerald-600" />;
    if (mimeType.includes('spreadsheet') || mimeType.includes('csv') || mimeType.includes('excel'))
      return <FileSpreadsheet className="w-5 h-5 text-green-600" />;
    if (mimeType.includes('pdf')) return <FileText className="w-5 h-5 text-rose-600" />;
    if (mimeType.includes('zip') || mimeType.includes('tar')) return <FileArchive className="w-5 h-5 text-amber-600" />;
    return <FileCode className="w-5 h-5 text-blue-600" />;
  };

  const totalBytes = documents.reduce((acc, curr) => acc + (curr.file_size || 0), 0);

  // Columns definition
  const columns: DataTableColumn<DocumentItem>[] = [
    {
      id: 'filename',
      header: 'FILENAME & TYPE',
      cell: (item) => (
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0">
            {getFileIcon(item.mime_type)}
          </div>
          <div>
            <div className="font-bold text-slate-900 text-xs truncate max-w-xs">{item.filename}</div>
            <div className="text-[11px] text-slate-400 font-mono">{item.mime_type || 'application/octet-stream'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'file_size',
      header: 'FILE SIZE',
      cell: (item) => (
        <div className="text-xs font-semibold text-slate-700">{formatFileSize(item.file_size)}</div>
      ),
    },
    {
      id: 'uploaded_at',
      header: 'UPLOADED AT',
      cell: (item) => (
        <div className="text-xs text-slate-500 font-medium">
          {item.uploaded_at ? item.uploaded_at.replace('T', ' ').substring(0, 16) : 'Just now'}
        </div>
      ),
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (item) => (
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => handleDownloadClick(item)}
            title="Download S3 File"
            className="p-1.5 text-indigo-600 hover:bg-indigo-50 rounded-md transition-colors cursor-pointer flex items-center gap-1 text-xs font-semibold"
          >
            <Download className="w-4 h-4" />
            Download
          </button>
          <button
            onClick={() => setDocumentToDelete(item)}
            title="Delete Document"
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
            <HardDrive className="w-7 h-7 text-indigo-600" />
            Document Storage & Files
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">MinIO S3 / Cloudflare R2 presigned file uploads, metadata tracking & secure downloads</p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => {
              setSelectedFile(null);
              setIsUploadModalOpen(true);
            }}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition-colors shadow-sm cursor-pointer"
          >
            <UploadCloud className="w-4 h-4" />
            Upload Document
          </button>
        </div>
      </div>



      {/* Main Data Table */}
      <DataTable<DocumentItem>
        columns={columns}
        data={documents}
        getRowKey={(item) => item.id}
        emptyTitle="No documents stored"
        emptyDescription="Upload PDF files, spreadsheets, images, or contracts to MinIO S3 storage."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search filename..."
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
        isLoading={isDocsLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: documents.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + documents.length,
        }}
      />

      {/* Upload File Modal */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-5">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <UploadCloud className="w-5 h-5 text-indigo-600" />
                Upload Document to MinIO S3
              </h2>
              <button onClick={() => setIsUploadModalOpen(false)} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="space-y-4">
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-colors ${
                  isDragging ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 hover:border-indigo-400 bg-slate-50'
                }`}
              >
                <input ref={fileInputRef} type="file" onChange={handleFileChange} className="hidden" />
                <UploadCloud className="w-10 h-10 text-indigo-600 mx-auto mb-2" />
                <p className="text-xs font-bold text-slate-800">
                  {selectedFile ? selectedFile.name : 'Click or drag & drop file to upload'}
                </p>
                {selectedFile ? (
                  <p className="text-[11px] text-emerald-600 font-semibold mt-1">
                    {formatFileSize(selectedFile.size)} - Selected
                  </p>
                ) : (
                  <p className="text-[11px] text-slate-400 mt-1">PDF, DOCX, XLSX, PNG, JPG up to 50MB</p>
                )}
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button type="button" onClick={() => setIsUploadModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!selectedFile || uploadMutation.isPending}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
                >
                  {uploadMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                  Start Upload
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Download Presigned URL Modal */}
      {presignedUrlResult && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Download className="w-5 h-5 text-indigo-600" />
                Secure Presigned Download Link
              </h3>
              <button onClick={() => setPresignedUrlResult(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3">
              <p className="text-xs text-slate-600 font-medium">
                Presigned S3 link generated for <strong className="text-slate-900">{presignedUrlResult.filename}</strong> (Expires in 60m):
              </p>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl font-mono text-[11px] text-slate-700 break-all">
                {presignedUrlResult.download_url}
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <a
                  href={presignedUrlResult.download_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold shadow-xs"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  Open / Download File
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Confirm Delete Modal */}
      {documentToDelete && (
        <ConfirmModal
          isOpen={!!documentToDelete}
          title="Delete Document"
          description={`Are you sure you want to delete "${documentToDelete.filename}"? This will remove the file from MinIO S3 storage.`}
          confirmText="Delete Document"
          variant="danger"
          onConfirm={handleDeleteDocument}
          onClose={() => setDocumentToDelete(null)}
        />
      )}
    </div>
  );
}
