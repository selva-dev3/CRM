'use client';

import { useRef, useState } from 'react';
import { Download, FolderOpen, Trash2, UploadCloud } from 'lucide-react';

import { ModuleError, PageNavigator } from '@/components/common/module-page-state';
import { useHasPermission } from '@/hooks/use-has-permission';
import { downloadDocumentApi, useDeleteDocumentMutation, useDocumentsQuery, useUploadRelatedDocumentMutation } from '@/lib/api/documents';
import { useProjectQuery, useProjectsPageQuery } from '@/lib/api/projects';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

const LIMIT = 20;

export default function ProjectDocumentsPage() {
  const { hasPermission } = useHasPermission();
  const input = useRef<HTMLInputElement>(null);
  const [projectId, setProjectId] = useState('');
  const [projectSearch, setProjectSearch] = useState('');
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');
  const projects = useProjectsPageQuery({ page: 1, limit: 50, search: projectSearch || undefined });
  const selectedProject = useProjectQuery(projectId);
  const projectOptions = projects.data?.items ?? [];
  const selectedProjectIsHidden = Boolean(
    selectedProject.data && !projectOptions.some((project) => project.id === projectId),
  );
  const documents = useDocumentsQuery({ page, limit: LIMIT, project_id: projectId || undefined, project_linked: true });
  const upload = useUploadRelatedDocumentMutation();
  const remove = useDeleteDocumentMutation();

  async function selectFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !projectId) return setError('Select a project before uploading a file.');
    try {
      await upload.mutateAsync({ file, relations: { project_id: projectId } });
      setError('');
      if (input.current) input.current.value = '';
    } catch (reason) { setError(getErrorMessage(reason, 'Could not upload project document.')); }
  }

  async function download(id: string) {
    try {
      const result = await downloadDocumentApi(id);
      window.open(result.download_url, '_blank', 'noopener,noreferrer');
      setError('');
    } catch (reason) { setError(getErrorMessage(reason, 'Could not download document.')); }
  }

  async function deleteDocument(id: string) {
    try { await remove.mutateAsync(id); setError(''); }
    catch (reason) { setError(getErrorMessage(reason, 'Could not delete document.')); }
  }

  return <div className="space-y-6 pb-12">
    <header><h1 className="flex items-center gap-2 text-2xl font-bold"><FolderOpen className="text-indigo-600" />Project Documents</h1><p className="mt-1 text-sm text-slate-500">Secure files linked directly to their project.</p></header>
    <div className="grid gap-3 rounded-xl border bg-white p-4 sm:grid-cols-[1fr_1fr_auto]"><input aria-label="Search projects" className="h-10 rounded-lg border px-3" placeholder="Search projects…" value={projectSearch} onChange={(event) => setProjectSearch(event.target.value)} /><select aria-label="Filter documents by project" className="h-10 rounded-lg border px-3" value={projectId} onChange={(event) => { setProjectId(event.target.value); setPage(1); }}><option value="">All projects</option>{selectedProjectIsHidden && <option value={selectedProject.data!.id}>{selectedProject.data!.name}</option>}{projectOptions.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select>{hasPermission(PERMISSIONS.DOCUMENTS.UPLOAD) && <label className={`inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 font-semibold text-white ${!projectId || upload.isPending ? 'pointer-events-none opacity-50' : ''}`}><UploadCloud size={16}/>{upload.isPending ? 'Uploading…' : 'Upload'}<input ref={input} className="sr-only" type="file" onChange={selectFile} disabled={!projectId || upload.isPending}/></label>}</div>
    {error && <ModuleError message={error} />}
    {projects.isError && <ModuleError message="Projects could not be loaded." retry={() => projects.refetch()} />}
    {documents.isError && <ModuleError message="Project documents could not be loaded." retry={() => documents.refetch()} />}
    <div className="overflow-x-auto rounded-xl border bg-white"><table className="min-w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="p-4">File</th><th className="p-4">Project</th><th className="p-4">Size</th><th className="p-4">Uploaded</th><th className="p-4">Actions</th></tr></thead><tbody>{documents.data?.items.map((document) => <tr key={document.id} className="border-t"><td className="p-4 font-semibold">{document.filename}</td><td className="p-4">{projects.data?.items.find((project) => project.id === document.project_id)?.name ?? document.project_id}</td><td className="p-4">{Math.ceil((document.file_size ?? 0) / 1024)} KB</td><td className="p-4">{document.uploaded_at?.slice(0,10)}</td><td className="p-4"><div className="flex gap-3"><button aria-label={`Download ${document.filename}`} className="text-indigo-600" onClick={() => download(document.id)}><Download size={16}/></button>{hasPermission(PERMISSIONS.DOCUMENTS.DELETE) && <button disabled={remove.isPending} aria-label={`Delete ${document.filename}`} className="text-rose-600 disabled:opacity-50" onClick={() => deleteDocument(document.id)}><Trash2 size={16}/></button>}</div></td></tr>)}</tbody></table>{documents.isLoading && <p className="p-8 text-center text-slate-500">Loading project documents…</p>}{!documents.isLoading && !documents.isError && !documents.data?.items.length && <p className="p-8 text-center text-slate-500">No project documents found.</p>}<PageNavigator page={page} total={documents.data?.total ?? 0} limit={LIMIT} onChange={setPage}/></div>
  </div>;
}
