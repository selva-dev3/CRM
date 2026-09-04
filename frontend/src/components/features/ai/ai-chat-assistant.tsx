'use client';

import React, { useState } from 'react';
import { LoaderCircle, Sparkles, X } from 'lucide-react';
import { useHasPermission } from '@/hooks/use-has-permission';
import type { AIActionProposal, AIEvidence, AIResultBlock } from '@/lib/api/ai';
import { aiService } from '@/lib/api/ai';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

interface ChatMessage {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  actions?: AIActionProposal[];
  evidence?: AIEvidence[];
  resultBlocks?: AIResultBlock[];
  followUpQuestions?: string[];
}

const entityRoutes: Record<string, string> = {
  lead: '/leads',
  contact: '/contacts',
  company: '/companies',
  deal: '/deals',
  task: '/tasks',
  project: '/projects',
  call: '/calls',
  meeting: '/meetings',
  document: '/documents',
  product: '/products',
  quote: '/quotes',
  invoice: '/invoices',
};

function ResultValue({ value }: { readonly value: unknown }) {
  if (value === null || value === undefined || value === '') return <span>—</span>;
  if (typeof value === 'object') return <span>{JSON.stringify(value)}</span>;
  return <span>{String(value)}</span>;
}

export function AIChatAssistant() {
  const { hasPermission } = useHasPermission();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [conversationId, setConversationId] = useState<string>();
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string>();
  const [executingActionId, setExecutingActionId] = useState<string>();
  const [executedActionIds, setExecutedActionIds] = useState<Set<string>>(new Set());

  const handleConfirmAction = async (proposalId: string) => {
    if (executingActionId) return;
    setExecutingActionId(proposalId);
    setError(undefined);
    try {
      await aiService.confirmAction(proposalId);
      setExecutedActionIds((previous) => new Set(previous).add(proposalId));
    } catch (requestError: unknown) {
      setError(getErrorMessage(requestError, 'The AI action could not be completed.'));
    } finally {
      setExecutingActionId(undefined);
    }
  };

  const sendMessage = async (rawMessage: string) => {
    const message = rawMessage.trim();
    if (!message || isSending) return;
    setMessages((previous) => [
      ...previous,
      { id: crypto.randomUUID(), sender: 'user', text: message },
    ]);
    setInput('');
    setError(undefined);
    setIsSending(true);
    try {
      const response = await aiService.chatAssistant(message, conversationId);
      setConversationId(response.conversation_id);
      setMessages((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          sender: 'ai',
          text: response.response,
          actions: response.proposed_actions,
          evidence: response.evidence,
          resultBlocks: response.result_blocks ?? [],
          followUpQuestions: response.follow_up_questions ?? [],
        },
      ]);
    } catch (requestError: unknown) {
      setError(getErrorMessage(requestError, 'The AI assistant is currently unavailable.'));
    } finally {
      setIsSending(false);
    }
  };

  const handleSend = () => void sendMessage(input);

  if (!hasPermission(PERMISSIONS.AI.GENERATE)) return null;

  return (
    <div className="fixed bottom-[max(1rem,env(safe-area-inset-bottom))] right-[max(1rem,env(safe-area-inset-right))] z-50">
      {!isOpen ? (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          title="AI Sales Assistant"
          aria-label="Open AI Sales Assistant"
          className="bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white rounded-full w-12 h-12 sm:w-14 sm:h-14 shadow-lg flex items-center justify-center transition cursor-pointer"
        >
          <Sparkles className="w-6 h-6" />
        </button>
      ) : (
        <div className="flex h-[min(36rem,calc(100dvh-2rem))] w-[calc(100vw-2rem)] max-w-md flex-col rounded-xl border border-gray-800 bg-gray-900 p-4 shadow-2xl sm:w-[28rem]">
          <div className="flex justify-between items-center pb-2 border-b border-gray-800">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <span>AI Sales Assistant</span>
            </h3>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-white cursor-pointer transition p-1"
              aria-label="Close AI Sales Assistant"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto my-2 space-y-2 text-sm text-gray-300">
            {messages.length === 0 && (
              <p className="text-gray-500 italic text-center mt-10">How can I assist your sales team today?</p>
            )}
            {messages.map((message) => (
              <div key={message.id} className={`p-2 rounded ${message.sender === 'user' ? 'bg-indigo-600 text-white self-end' : 'bg-gray-800 text-gray-200'}`}>
                <p>{message.text}</p>
                {message.resultBlocks?.map((block) => (
                  <section key={block.key} className="mt-2 rounded border border-gray-700 bg-gray-950/40 p-2">
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium text-white">{block.title}</p>
                      <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-300">
                        {block.result_count}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-gray-400">{block.explanation}</p>
                    <p className="mt-1 text-[10px] text-gray-500">
                      Data retrieved {new Date(block.generated_at).toLocaleString()}
                    </p>
                    {block.results.slice(0, 5).map((result, resultIndex) => (
                      <dl key={String(result.id ?? resultIndex)} className="mt-2 border-t border-gray-800 pt-1 text-xs">
                        {Object.entries(result).map(([key, value]) => (
                          <div key={key} className="grid grid-cols-[5.5rem_1fr] gap-2 py-0.5">
                            <dt className="truncate capitalize text-gray-500">{key.replaceAll('_', ' ')}</dt>
                            <dd className="break-words text-gray-200"><ResultValue value={value} /></dd>
                          </div>
                        ))}
                      </dl>
                    ))}
                  </section>
                ))}
                {message.evidence && message.evidence.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1" aria-label="Answer sources">
                    {message.evidence.map((evidence) => {
                      const route = entityRoutes[evidence.entity_type];
                      const label = evidence.label || `${evidence.entity_type} source`;
                      return route ? (
                        <a
                          key={`${evidence.entity_type}-${evidence.entity_id}`}
                          href={`${route}/${encodeURIComponent(evidence.entity_id)}`}
                          className="rounded bg-indigo-950 px-2 py-1 text-xs text-indigo-200 hover:bg-indigo-900"
                        >
                          {label}
                        </a>
                      ) : (
                        <span key={`${evidence.entity_type}-${evidence.entity_id}`} className="rounded bg-gray-700 px-2 py-1 text-xs">
                          {label}
                        </span>
                      );
                    })}
                  </div>
                )}
                {message.followUpQuestions && message.followUpQuestions.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {message.followUpQuestions.map((question) => (
                      <button
                        key={question}
                        type="button"
                        onClick={() => void sendMessage(question)}
                        disabled={isSending}
                        className="block w-full rounded border border-gray-700 px-2 py-1 text-left text-xs text-gray-300 hover:bg-gray-800 disabled:opacity-50"
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                )}
                {message.actions?.map((action) => {
                  if (!action.proposal_id || action.action_type !== 'create_task') return null;
                  const proposalId = action.proposal_id;
                  const executed = executedActionIds.has(proposalId);
                  return (
                    <div key={proposalId} className="mt-2 rounded border border-gray-700 p-2">
                      <p className="font-medium text-white">{action.title}</p>
                      {hasPermission(PERMISSIONS.TASKS.CREATE) ? (
                        <button
                          type="button"
                          onClick={() => handleConfirmAction(proposalId)}
                          disabled={executed || Boolean(executingActionId)}
                          className="mt-2 rounded bg-indigo-600 px-2 py-1 text-xs text-white disabled:opacity-50"
                        >
                          {executed
                            ? 'Task created'
                            : executingActionId === proposalId
                              ? 'Creating…'
                              : 'Confirm task'}
                        </button>
                      ) : (
                        <p className="mt-1 text-xs text-gray-400">Missing task creation permission.</p>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
            {isSending && (
              <div className="flex items-center gap-2 rounded bg-gray-800 p-2 text-gray-300" role="status">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                Analyzing authorized CRM data…
              </div>
            )}
            {error && <p className="rounded bg-red-950 p-2 text-red-200" role="alert">{error}</p>}
          </div>
          <div className="flex gap-2 pt-2 border-t border-gray-800">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask AI..."
              aria-label="Message AI Sales Assistant"
              disabled={isSending}
              className="min-w-0 flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1 text-sm text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={isSending || !input.trim()}
              className="bg-indigo-600 hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50 text-white px-3 py-1 rounded text-sm cursor-pointer"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
