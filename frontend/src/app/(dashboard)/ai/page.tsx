'use client';

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from 'react';
import {
  Bot, ChevronRight, Loader2, Menu, MessageSquare, Plus, RotateCcw,
  Send, Sparkles, Trash2, UserRound, X,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useHasPermission } from '@/hooks/use-has-permission';
import {
  aiService,
  type AIActionProposal,
  type AIConversationSummary,
  type AIEvidence,
  type AIResultBlock,
} from '@/lib/api/ai';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  resultBlocks?: AIResultBlock[];
  evidence?: AIEvidence[];
  actions?: AIActionProposal[];
  followUps?: string[];
  model?: string | null;
  fallbackUsed?: boolean;
  pending?: boolean;
  failed?: boolean;
}

const entityRoutes: Record<string, string> = {
  lead: '/leads', contact: '/contacts', company: '/companies', deal: '/deals',
  task: '/tasks', project: '/projects', call: '/calls', meeting: '/meetings',
  document: '/documents', product: '/products', quote: '/quotes', invoice: '/invoices',
};

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function ResultBlock({ block }: { readonly block: AIResultBlock }) {
  const columns = Array.from(
    new Set(block.results.flatMap((record) => Object.keys(record))),
  ).slice(0, 8);
  return (
    <section className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{block.title}</h3>
          <p className="mt-1 text-xs text-slate-500">{block.explanation}</p>
        </div>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
          {block.result_count}
        </span>
      </div>
      {block.results.length > 0 && (
        <div className="max-h-80 overflow-auto">
          <table className="min-w-full text-left text-xs">
            <thead className="sticky top-0 bg-slate-50 text-slate-500">
              <tr>{columns.map((column) => <th key={column} className="whitespace-nowrap px-4 py-2 font-medium capitalize">{column.replaceAll('_', ' ')}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {block.results.slice(0, 20).map((record, index) => (
                <tr key={String(record.id ?? index)}>
                  {columns.map((column) => <td key={column} className="max-w-64 break-words px-4 py-2 text-slate-700">{displayValue(record[column])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function AssistantMessage({
  message,
  onFollowUp,
  onConfirm,
  executingActionId,
  executedActionIds,
}: {
  readonly message: ChatMessage;
  readonly onFollowUp: (question: string) => void;
  readonly onConfirm: (proposalId: string) => void;
  readonly executingActionId?: string;
  readonly executedActionIds: Set<string>;
}) {
  return (
    <div className="group flex gap-3 py-5">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-white"><Bot className="h-4 w-4" /></div>
      <div className="min-w-0 flex-1">
        <div className="whitespace-pre-wrap text-sm leading-7 text-slate-800">
          {message.text || (message.pending ? 'Thinking…' : '')}
          {message.pending && <span className="ml-1 inline-block h-4 w-1 animate-pulse bg-indigo-500" />}
        </div>
        {message.resultBlocks?.map((block) => <ResultBlock key={block.key} block={block} />)}
        {!!message.evidence?.length && (
          <div className="mt-3 flex flex-wrap gap-2" aria-label="Answer sources">
            {message.evidence.map((source) => {
              const route = entityRoutes[source.entity_type];
              const content = <>{source.label}<ChevronRight className="h-3 w-3" /></>;
              return route
                ? <a key={`${source.entity_type}-${source.entity_id}`} href={`${route}/${encodeURIComponent(source.entity_id)}`} className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50">{content}</a>
                : <span key={`${source.entity_type}-${source.entity_id}`} className="rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-600">{source.label}</span>;
            })}
          </div>
        )}
        {!!message.actions?.length && (
          <div className="mt-4 space-y-2">
            {message.actions.map((action) => action.proposal_id && (
              <div key={action.proposal_id} className="flex items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2">
                <span className="text-xs text-amber-900">{action.title}</span>
                <Button type="button" size="sm" variant="outline" disabled={executingActionId === action.proposal_id || executedActionIds.has(action.proposal_id)} onClick={() => onConfirm(action.proposal_id!)}>
                  {executedActionIds.has(action.proposal_id) ? 'Confirmed' : executingActionId === action.proposal_id ? 'Confirming…' : 'Confirm'}
                </Button>
              </div>
            ))}
          </div>
        )}
        {!!message.followUps?.length && (
          <div className="mt-4 flex flex-wrap gap-2">
            {message.followUps.map((question) => <button key={question} type="button" onClick={() => onFollowUp(question)} className="rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1.5 text-xs text-indigo-700 hover:bg-indigo-100">{question}</button>)}
          </div>
        )}
        {!message.pending && message.model && (
          <p className="mt-3 text-[11px] text-slate-400">
            {message.fallbackUsed ? 'Fallback model used · ' : ''}{message.model}
          </p>
        )}
      </div>
    </div>
  );
}

export default function AIIntelligencePage() {
  const { hasPermission } = useHasPermission();
  const canRead = hasPermission(PERMISSIONS.AI.READ);
  const canGenerate = hasPermission(PERMISSIONS.AI.GENERATE);
  const [conversations, setConversations] = useState<AIConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);
  const [status, setStatus] = useState<string>();
  const [error, setError] = useState<string>();
  const [lastQuestion, setLastQuestion] = useState<string>();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [executingActionId, setExecutingActionId] = useState<string>();
  const [executedActionIds, setExecutedActionIds] = useState<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadConversations = async () => {
    if (!canRead) return;
    try { setConversations(await aiService.listConversations()); }
    catch (requestError) { setError(getErrorMessage(requestError, 'Chat history could not be loaded.')); }
    finally { setIsHistoryLoading(false); }
  };

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    aiService.listConversations()
      .then((items) => { if (active) setConversations(items); })
      .catch((requestError) => {
        if (active) setError(getErrorMessage(requestError, 'Chat history could not be loaded.'));
      })
      .finally(() => { if (active) setIsHistoryLoading(false); });
    return () => { active = false; };
  }, [canRead]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, status]);

  const newChat = () => {
    setConversationId(undefined);
    setMessages([]);
    setError(undefined);
    setStatus(undefined);
    setSidebarOpen(false);
  };

  const openConversation = async (id: string) => {
    setError(undefined);
    setStatus('Loading conversation…');
    try {
      const conversation = await aiService.getConversation(id);
      setConversationId(id);
      setMessages(conversation.messages.flatMap((message) => [
        { id: `${message.id}-user`, role: 'user' as const, text: message.user_prompt },
        {
          id: `${message.id}-assistant`, role: 'assistant' as const,
          text: message.ai_response, resultBlocks: message.result_blocks,
          evidence: message.evidence, followUps: message.follow_up_questions,
          model: message.model, fallbackUsed: message.fallback_used,
        },
      ]));
      setSidebarOpen(false);
    } catch (requestError) {
      setError(getErrorMessage(requestError, 'Conversation could not be loaded.'));
    } finally { setStatus(undefined); }
  };

  const deleteConversation = async (id: string) => {
    try {
      await aiService.deleteConversation(id);
      if (conversationId === id) newChat();
      setConversations((items) => items.filter((item) => item.id !== id));
    } catch (requestError) {
      setError(getErrorMessage(requestError, 'Conversation could not be deleted.'));
    }
  };

  const confirmAction = async (proposalId: string) => {
    if (executingActionId) return;
    setExecutingActionId(proposalId);
    setError(undefined);
    try {
      await aiService.confirmAction(proposalId);
      setExecutedActionIds((items) => new Set(items).add(proposalId));
    } catch (requestError) {
      setError(getErrorMessage(requestError, 'The proposed CRM action could not be completed.'));
    } finally { setExecutingActionId(undefined); }
  };

  const sendMessage = async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || isSending || !canGenerate) return;
    const userId = crypto.randomUUID();
    const assistantId = crypto.randomUUID();
    setMessages((items) => [
      ...items,
      { id: userId, role: 'user', text: trimmed },
      { id: assistantId, role: 'assistant', text: '', pending: true },
    ]);
    setInput('');
    setError(undefined);
    setLastQuestion(trimmed);
    setIsSending(true);
    try {
      const result = await aiService.streamChatAssistant(trimmed, conversationId, {
        onStatus: setStatus,
        onFallback: setStatus,
        onDelta: (text) => setMessages((items) => items.map((item) =>
          item.id === assistantId ? { ...item, text: item.text + text } : item)),
      });
      setConversationId(result.conversation_id);
      setMessages((items) => items.map((item) => item.id === assistantId ? {
        ...item,
        text: result.response,
        pending: false,
        resultBlocks: result.result_blocks,
        evidence: result.evidence,
        actions: result.proposed_actions,
        followUps: result.follow_up_questions,
        model: result.metadata?.model,
        fallbackUsed: result.metadata?.fallback_used,
      } : item));
      await loadConversations();
    } catch (requestError) {
      setMessages((items) => items.map((item) =>
        item.id === assistantId
          ? { ...item, pending: false, failed: true, text: 'I could not complete that request.' }
          : item,
      ));
      setError(getErrorMessage(requestError, 'The AI assistant is temporarily unavailable.'));
    } finally {
      setIsSending(false);
      setStatus(undefined);
    }
  };

  const submit = (event: FormEvent) => { event.preventDefault(); void sendMessage(input); };
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(input);
    }
  };

  if (!canRead) {
    return <div className="flex min-h-[60vh] items-center justify-center text-sm text-slate-500">You do not have permission to access AI conversations.</div>;
  }

  return (
    <div className="relative -m-4 flex h-[calc(100dvh-4.5rem)] overflow-hidden bg-white sm:-m-6">
      {sidebarOpen && <button type="button" aria-label="Close chat history" className="absolute inset-0 z-20 bg-slate-950/30 md:hidden" onClick={() => setSidebarOpen(false)} />}
      <aside className={`absolute inset-y-0 left-0 z-30 flex w-72 flex-col border-r border-slate-200 bg-slate-50 transition-transform md:static md:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex items-center gap-2 p-3">
          <Button type="button" onClick={newChat} className="flex-1 justify-start gap-2 bg-white text-slate-800 shadow-sm hover:bg-slate-100" variant="outline"><Plus className="h-4 w-4" />New chat</Button>
          <button type="button" className="rounded-lg p-2 text-slate-500 md:hidden" onClick={() => setSidebarOpen(false)} aria-label="Close chat history"><X className="h-5 w-5" /></button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-4">
          <p className="px-2 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Recent chats</p>
          {isHistoryLoading && <div className="flex items-center gap-2 px-3 py-3 text-xs text-slate-500"><Loader2 className="h-3.5 w-3.5 animate-spin" />Loading history</div>}
          {!isHistoryLoading && conversations.length === 0 && <p className="px-3 py-4 text-xs leading-5 text-slate-400">Your CRM conversations will appear here.</p>}
          {conversations.map((conversation) => (
            <div key={conversation.id} className={`group mb-1 flex items-center rounded-lg ${conversation.id === conversationId ? 'bg-slate-200' : 'hover:bg-slate-100'}`}>
              <button type="button" onClick={() => void openConversation(conversation.id)} className="min-w-0 flex-1 px-3 py-2.5 text-left"><span className="block truncate text-sm text-slate-700">{conversation.title}</span><span className="mt-0.5 block text-[10px] text-slate-400">{new Date(conversation.updated_at).toLocaleDateString()}</span></button>
              <button type="button" aria-label={`Delete ${conversation.title}`} onClick={() => void deleteConversation(conversation.id)} className="mr-2 rounded p-1.5 text-slate-400 opacity-0 hover:bg-white hover:text-red-600 group-hover:opacity-100 focus:opacity-100"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          ))}
        </div>
        <div className="border-t border-slate-200 px-4 py-3 text-[11px] leading-4 text-slate-400">Answers use only CRM records your role can access.</div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-100 px-4 sm:px-6">
          <button type="button" onClick={() => setSidebarOpen(true)} className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 md:hidden" aria-label="Open chat history"><Menu className="h-5 w-5" /></button>
          <Sparkles className="h-5 w-5 text-indigo-600" />
          <div><h1 className="text-sm font-semibold text-slate-900">CRM AI</h1><p className="text-[11px] text-slate-400">Authorized, live CRM answers</p></div>
        </header>

        <div className="flex-1 overflow-y-auto px-4 sm:px-8">
          <div className="mx-auto max-w-4xl">
            {messages.length === 0 && (
              <div className="flex min-h-[55vh] flex-col items-center justify-center text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600"><MessageSquare className="h-6 w-6" /></div>
                <h2 className="mt-5 text-2xl font-semibold tracking-tight text-slate-900">Ask about your CRM</h2>
                <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">Get counts, lists, summaries, comparisons, dates, amounts, and related data from records you are authorized to view.</p>
                <div className="mt-6 grid w-full max-w-2xl gap-2 sm:grid-cols-2">
                  {['How many open deals are there?', 'Show companies not contacted recently', 'Which projects are active?', 'Summarize this month’s new leads'].map((example) => <button key={example} type="button" onClick={() => void sendMessage(example)} disabled={!canGenerate} className="rounded-xl border border-slate-200 px-4 py-3 text-left text-sm text-slate-600 transition hover:border-indigo-200 hover:bg-indigo-50/50 disabled:opacity-50">{example}</button>)}
                </div>
              </div>
            )}
            {messages.map((message) => message.role === 'user' ? (
              <div key={message.id} className="flex justify-end gap-3 py-5"><div className="max-w-[85%] rounded-2xl bg-slate-100 px-4 py-3 text-sm leading-6 text-slate-800">{message.text}</div><div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-white"><UserRound className="h-4 w-4" /></div></div>
            ) : <AssistantMessage key={message.id} message={message} onFollowUp={(question) => void sendMessage(question)} onConfirm={(proposalId) => void confirmAction(proposalId)} executingActionId={executingActionId} executedActionIds={executedActionIds} />)}
            {status && <div className="flex items-center gap-2 pb-3 text-xs text-indigo-600" aria-live="polite"><Loader2 className="h-3.5 w-3.5 animate-spin" />{status}</div>}
            {error && <div className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700"><span>{error}</span>{lastQuestion && <Button type="button" size="sm" variant="outline" onClick={() => void sendMessage(lastQuestion)} disabled={isSending} className="gap-1.5"><RotateCcw className="h-3.5 w-3.5" />Retry</Button>}</div>}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="shrink-0 border-t border-slate-100 bg-white px-4 py-3 sm:px-8 sm:py-4">
          <form onSubmit={submit} className="mx-auto max-w-4xl">
            <div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-100">
              <textarea aria-label="Message CRM AI" value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={handleKeyDown} rows={1} maxLength={4000} placeholder={canGenerate ? 'Ask anything about your CRM…' : 'You need ai:generate permission to ask questions'} disabled={!canGenerate || isSending} className="max-h-36 min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-sm text-slate-800 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed" />
              <Button type="submit" size="icon" aria-label="Send message" disabled={!canGenerate || !input.trim() || isSending} className="h-10 w-10 shrink-0 rounded-xl bg-indigo-600 hover:bg-indigo-700">{isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}</Button>
            </div>
            <p className="mt-2 text-center text-[10px] text-slate-400">CRM AI can make mistakes. Verify important decisions against the linked source records.</p>
          </form>
        </div>
      </section>
    </div>
  );
}
