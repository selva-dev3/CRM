'use client';

import { type FormEvent, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, ArrowLeft, BookOpenCheck, MessageSquareText, Paperclip, Send, Trash2 } from 'lucide-react';
import { useParams } from 'next/navigation';

import { ModuleError } from '@/components/common/module-page-state';
import { PermissionGate } from '@/components/common/permission-gate';
import { PageNavigator } from '@/components/common/module-page-state';
import { UserSelect } from '@/components/common/user-select';
import { Button } from '@/components/ui/button';
import { useHasPermission } from '@/hooks/use-has-permission';
import {
  useAddTicketComment,
  useArticles,
  useEscalateTicket,
  useLinkTicketArticle,
  useTicket,
  useTicketArticles,
  useTicketAttachments,
  useTicketComments,
  useUnlinkTicketArticle,
  useUpdateTicket,
  useUploadTicketAttachment,
} from '@/lib/api/crm-extensions';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

export default function TicketDetailPage() {
  const id = String(useParams<{ id: string }>().id ?? '');
  const [comment, setComment] = useState('');
  const [isInternal, setIsInternal] = useState(true);
  const [articleId, setArticleId] = useState('');
  const [error, setError] = useState('');
  const [commentPage, setCommentPage] = useState(1);
  const [attachmentPage, setAttachmentPage] = useState(1);
  const [escalationReason, setEscalationReason] = useState('');
  const { hasPermission } = useHasPermission();
  const canReadKnowledgeBase = hasPermission(PERMISSIONS.KNOWLEDGE_BASE.READ);
  const ticket = useTicket(id);
  const comments = useTicketComments(id, commentPage);
  const canReadDocuments = hasPermission(PERMISSIONS.DOCUMENTS.READ);
  const canUploadDocuments = hasPermission(PERMISSIONS.DOCUMENTS.UPLOAD);
  const canAssign = hasPermission(PERMISSIONS.TICKETS.ASSIGN) && hasPermission(PERMISSIONS.USERS.READ);
  const attachments = useTicketAttachments(id, attachmentPage, canReadDocuments);
  const linkedArticles = useTicketArticles(id, canReadKnowledgeBase);
  const articles = useArticles(1, '', 'Published', canReadKnowledgeBase);
  const update = useUpdateTicket();
  const addComment = useAddTicketComment();
  const linkArticle = useLinkTicketArticle();
  const unlinkArticle = useUnlinkTicketArticle();
  const escalate = useEscalateTicket();
  const uploadAttachment = useUploadTicketAttachment();

  async function submitComment(event: FormEvent) {
    event.preventDefault();
    try {
      await addComment.mutateAsync({ ticketId: id, body: comment.trim(), isInternal });
      setComment(''); setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not add the comment.'));
    }
  }

  async function submitArticle(event: FormEvent) {
    event.preventDefault();
    if (!articleId) return;
    try {
      await linkArticle.mutateAsync({ ticketId: id, articleId });
      setArticleId(''); setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not link the article.'));
    }
  }

  async function changeStatus(status: string) {
    try {
      await update.mutateAsync({ id, payload: { status } });
      setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not update ticket status.'));
    }
  }

  async function assignTo(userId: string) {
    try {
      await update.mutateAsync({ id, payload: { assigned_to: userId || null } });
      setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not assign the ticket.'));
    }
  }

  async function escalateTicket() {
    if (!escalationReason.trim()) return;
    try {
      await escalate.mutateAsync({ ticketId: id, reason: escalationReason.trim() });
      setEscalationReason(''); setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not escalate the ticket.'));
    }
  }

  async function upload(file: File | undefined) {
    if (!file) return;
    try {
      await uploadAttachment.mutateAsync({ ticketId: id, file });
      setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not upload the attachment.'));
    }
  }

  async function unlink(articleId: string) {
    try {
      await unlinkArticle.mutateAsync({ ticketId: id, articleId });
      setError('');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Could not unlink the article.'));
    }
  }

  if (ticket.isLoading) return <p className="p-6 text-sm text-slate-500">Loading ticket…</p>;
  if (ticket.isError || !ticket.data) return <ModuleError message="Ticket could not be loaded." retry={() => ticket.refetch()} />;
  const record = ticket.data;

  return <div className="space-y-6 pb-12">
    <Link href="/tickets" className="inline-flex items-center gap-2 text-sm font-semibold text-indigo-700"><ArrowLeft className="size-4" />Back to tickets</Link>
    {error && <ModuleError message={error} />}
    <section className="rounded-xl border bg-white p-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm font-semibold text-indigo-700">{record.ticket_number}</p><h1 className="text-2xl font-bold">{record.subject}</h1><p className="mt-3 whitespace-pre-wrap text-sm text-slate-600">{record.description}</p></div><PermissionGate permission={PERMISSIONS.TICKETS.UPDATE}><select aria-label="Ticket status" className="h-10 rounded-md border px-3" value={record.status} disabled={update.isPending} onChange={(event) => void changeStatus(event.target.value)}>{['New', 'Open', 'Pending', 'Resolved', 'Closed'].map((value) => <option key={value}>{value}</option>)}</select></PermissionGate></div><dl className="mt-5 grid gap-3 text-sm sm:grid-cols-3"><div><dt className="text-slate-500">Priority</dt><dd className="font-semibold">{record.priority}</dd></div><div><dt className="text-slate-500">Created</dt><dd className="font-semibold">{new Date(record.created_at).toLocaleString()}</dd></div><div><dt className="text-slate-500">Resolution due</dt><dd className="font-semibold">{record.resolution_due_at ? new Date(record.resolution_due_at).toLocaleString() : 'Not configured'}</dd></div></dl>{canAssign && <div className="mt-5 grid gap-3 border-t pt-5 sm:grid-cols-2"><div><label className="mb-1 block text-xs font-semibold uppercase text-slate-500">Assigned support agent</label><UserSelect value={record.assigned_to || ''} onChange={(value) => void assignTo(value)} /></div><div><label htmlFor="escalation-reason" className="mb-1 block text-xs font-semibold uppercase text-slate-500">Escalation reason</label><div className="flex gap-2"><input id="escalation-reason" className="h-9 min-w-0 flex-1 rounded-md border px-3 text-sm" value={escalationReason} onChange={(event) => setEscalationReason(event.target.value)} /><Button size="sm" variant="outline" disabled={!escalationReason.trim() || escalate.isPending} onClick={() => void escalateTicket()}><AlertTriangle className="size-4" />Escalate</Button></div></div></div>}{record.escalated_at && <p className="mt-3 text-sm text-amber-700">Escalated {new Date(record.escalated_at).toLocaleString()}: {record.escalation_reason}</p>}</section>
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-xl border bg-white p-5"><h2 className="flex items-center gap-2 font-bold"><MessageSquareText className="size-5 text-indigo-600" />Conversation</h2><div className="my-4 space-y-3">{comments.isLoading && <p className="text-sm text-slate-500">Loading comments…</p>}{!comments.isLoading && !comments.data?.items.length && <p className="text-sm text-slate-500">No comments yet.</p>}{comments.data?.items.map((item) => <article key={item.id} className="rounded-lg bg-slate-50 p-3"><div className="flex justify-between gap-3 text-xs text-slate-500"><span>{item.is_internal ? 'Internal note' : 'Customer-visible reply'}</span><time>{new Date(item.created_at).toLocaleString()}</time></div><p className="mt-2 whitespace-pre-wrap text-sm">{item.body}</p></article>)}</div><PageNavigator page={commentPage} total={comments.data?.total ?? 0} limit={20} onChange={setCommentPage} /><PermissionGate permission={PERMISSIONS.TICKETS.UPDATE}><form onSubmit={submitComment} className="mt-4 space-y-3"><textarea required aria-label="Comment" className="min-h-28 w-full rounded-md border p-3 text-sm" value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add a response or internal note" /><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={isInternal} onChange={(event) => setIsInternal(event.target.checked)} />Internal note</label><Button disabled={!comment.trim() || addComment.isPending}><Send className="size-4" />Add comment</Button></form></PermissionGate></section>
      {canReadKnowledgeBase && <section className="rounded-xl border bg-white p-5"><h2 className="flex items-center gap-2 font-bold"><BookOpenCheck className="size-5 text-indigo-600" />Knowledge articles</h2><div className="my-4 space-y-2">{linkedArticles.isLoading && <p className="text-sm text-slate-500">Loading articles…</p>}{!linkedArticles.isLoading && !linkedArticles.data?.length && <p className="text-sm text-slate-500">No knowledge articles linked.</p>}{linkedArticles.data?.map((article) => <div key={article.id} className="flex items-center justify-between gap-3 rounded-lg border p-3"><div><p className="font-medium">{article.title}</p><p className="text-xs text-slate-500">{article.category || 'Uncategorized'}</p></div><PermissionGate permission={PERMISSIONS.TICKETS.UPDATE}><Button variant="ghost" size="icon" aria-label={`Unlink ${article.title}`} disabled={unlinkArticle.isPending} onClick={() => void unlink(article.id)}><Trash2 className="size-4 text-rose-600" /></Button></PermissionGate></div>)}</div><PermissionGate permission={PERMISSIONS.TICKETS.UPDATE}><form onSubmit={submitArticle} className="flex flex-col gap-3 sm:flex-row"><select aria-label="Knowledge article" className="h-10 min-w-0 flex-1 rounded-md border px-3" value={articleId} onChange={(event) => setArticleId(event.target.value)}><option value="">Select a published article</option>{articles.data?.items.filter((article) => !linkedArticles.data?.some((linked) => linked.id === article.id)).map((article) => <option key={article.id} value={article.id}>{article.title}</option>)}</select><Button disabled={!articleId || linkArticle.isPending}>Link article</Button></form></PermissionGate></section>}
    </div>
    {canReadDocuments && <section className="rounded-xl border bg-white p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 font-bold"><Paperclip className="size-5 text-indigo-600" />Attachments</h2><p className="mt-1 text-sm text-slate-500">Files linked to this support case.</p></div>{canUploadDocuments && <label className="cursor-pointer rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white"><input type="file" className="sr-only" disabled={uploadAttachment.isPending} onChange={(event) => void upload(event.target.files?.[0])} />{uploadAttachment.isPending ? 'Uploading…' : 'Upload file'}</label>}</div><div className="my-4 divide-y rounded-lg border">{attachments.isLoading && <p className="p-4 text-sm text-slate-500">Loading attachments…</p>}{!attachments.isLoading && !attachments.data?.items.length && <p className="p-4 text-sm text-slate-500">No attachments.</p>}{attachments.data?.items.map((item) => <a key={item.id} href={item.download_url} target="_blank" rel="noreferrer" className="flex items-center justify-between gap-3 p-3 text-sm text-indigo-700 hover:bg-slate-50"><span className="truncate">{item.filename}</span><span className="text-xs text-slate-500">{Math.ceil(item.file_size / 1024)} KB</span></a>)}</div><PageNavigator page={attachmentPage} total={attachments.data?.total ?? 0} limit={20} onChange={setAttachmentPage} /></section>}
  </div>;
}
