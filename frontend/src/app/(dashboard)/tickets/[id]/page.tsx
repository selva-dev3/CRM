'use client';

import { type FormEvent, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, BookOpenCheck, MessageSquareText, Send, Trash2 } from 'lucide-react';
import { useParams } from 'next/navigation';

import { ModuleError } from '@/components/common/module-page-state';
import { PermissionGate } from '@/components/common/permission-gate';
import { Button } from '@/components/ui/button';
import { useHasPermission } from '@/hooks/use-has-permission';
import {
  useAddTicketComment,
  useArticles,
  useLinkTicketArticle,
  useTicket,
  useTicketArticles,
  useTicketComments,
  useUnlinkTicketArticle,
  useUpdateTicket,
} from '@/lib/api/crm-extensions';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

export default function TicketDetailPage() {
  const id = String(useParams<{ id: string }>().id ?? '');
  const [comment, setComment] = useState('');
  const [isInternal, setIsInternal] = useState(true);
  const [articleId, setArticleId] = useState('');
  const [error, setError] = useState('');
  const { hasPermission } = useHasPermission();
  const canReadKnowledgeBase = hasPermission(PERMISSIONS.KNOWLEDGE_BASE.READ);
  const ticket = useTicket(id);
  const comments = useTicketComments(id);
  const linkedArticles = useTicketArticles(id, canReadKnowledgeBase);
  const articles = useArticles(1, '', 'Published', canReadKnowledgeBase);
  const update = useUpdateTicket();
  const addComment = useAddTicketComment();
  const linkArticle = useLinkTicketArticle();
  const unlinkArticle = useUnlinkTicketArticle();

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
    <section className="rounded-xl border bg-white p-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm font-semibold text-indigo-700">{record.ticket_number}</p><h1 className="text-2xl font-bold">{record.subject}</h1><p className="mt-3 whitespace-pre-wrap text-sm text-slate-600">{record.description}</p></div><PermissionGate permission={PERMISSIONS.TICKETS.UPDATE}><select aria-label="Ticket status" className="h-10 rounded-md border px-3" value={record.status} disabled={update.isPending} onChange={(event) => void changeStatus(event.target.value)}>{['New', 'Open', 'Pending', 'Resolved', 'Closed'].map((value) => <option key={value}>{value}</option>)}</select></PermissionGate></div><dl className="mt-5 grid gap-3 text-sm sm:grid-cols-3"><div><dt className="text-slate-500">Priority</dt><dd className="font-semibold">{record.priority}</dd></div><div><dt className="text-slate-500">Created</dt><dd className="font-semibold">{new Date(record.created_at).toLocaleString()}</dd></div><div><dt className="text-slate-500">Resolution due</dt><dd className="font-semibold">{record.resolution_due_at ? new Date(record.resolution_due_at).toLocaleString() : 'Not configured'}</dd></div></dl></section>
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-xl border bg-white p-5"><h2 className="flex items-center gap-2 font-bold"><MessageSquareText className="size-5 text-indigo-600" />Conversation</h2><div className="my-4 space-y-3">{comments.isLoading && <p className="text-sm text-slate-500">Loading comments…</p>}{!comments.isLoading && !comments.data?.length && <p className="text-sm text-slate-500">No comments yet.</p>}{comments.data?.map((item) => <article key={item.id} className="rounded-lg bg-slate-50 p-3"><div className="flex justify-between gap-3 text-xs text-slate-500"><span>{item.is_internal ? 'Internal note' : 'Customer-visible reply'}</span><time>{new Date(item.created_at).toLocaleString()}</time></div><p className="mt-2 whitespace-pre-wrap text-sm">{item.body}</p></article>)}</div><PermissionGate permission={PERMISSIONS.TICKETS.UPDATE}><form onSubmit={submitComment} className="space-y-3"><textarea required aria-label="Comment" className="min-h-28 w-full rounded-md border p-3 text-sm" value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add a response or internal note" /><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={isInternal} onChange={(event) => setIsInternal(event.target.checked)} />Internal note</label><Button disabled={!comment.trim() || addComment.isPending}><Send className="size-4" />Add comment</Button></form></PermissionGate></section>
      {canReadKnowledgeBase && <section className="rounded-xl border bg-white p-5"><h2 className="flex items-center gap-2 font-bold"><BookOpenCheck className="size-5 text-indigo-600" />Knowledge articles</h2><div className="my-4 space-y-2">{linkedArticles.isLoading && <p className="text-sm text-slate-500">Loading articles…</p>}{!linkedArticles.isLoading && !linkedArticles.data?.length && <p className="text-sm text-slate-500">No knowledge articles linked.</p>}{linkedArticles.data?.map((article) => <div key={article.id} className="flex items-center justify-between gap-3 rounded-lg border p-3"><div><p className="font-medium">{article.title}</p><p className="text-xs text-slate-500">{article.category || 'Uncategorized'}</p></div><PermissionGate permission={PERMISSIONS.TICKETS.UPDATE}><Button variant="ghost" size="icon" aria-label={`Unlink ${article.title}`} disabled={unlinkArticle.isPending} onClick={() => void unlink(article.id)}><Trash2 className="size-4 text-rose-600" /></Button></PermissionGate></div>)}</div><PermissionGate permission={PERMISSIONS.TICKETS.UPDATE}><form onSubmit={submitArticle} className="flex flex-col gap-3 sm:flex-row"><select aria-label="Knowledge article" className="h-10 min-w-0 flex-1 rounded-md border px-3" value={articleId} onChange={(event) => setArticleId(event.target.value)}><option value="">Select a published article</option>{articles.data?.items.filter((article) => !linkedArticles.data?.some((linked) => linked.id === article.id)).map((article) => <option key={article.id} value={article.id}>{article.title}</option>)}</select><Button disabled={!articleId || linkArticle.isPending}>Link article</Button></form></PermissionGate></section>}
    </div>
  </div>;
}
