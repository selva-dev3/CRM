'use client';

import { FormEvent, useEffect, useState } from 'react';
import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  Loader2,
  Mail,
  Search,
  Sparkles,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { Button, Card, Input, Label, Textarea } from '@/components/ui';
import { useHasPermission } from '@/hooks/use-has-permission';
import {
  aiService,
  type AIUsageStats,
  type CRMSearchResponse,
  type EmailGenerationResponse,
} from '@/lib/api/ai';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

type SearchScope = 'auto' | 'lead' | 'contact' | 'company' | 'deal' | 'task';

function ResultValue({ value }: { readonly value: unknown }) {
  if (value === null || value === undefined || value === '') return <span>—</span>;
  if (typeof value === 'object') return <span>{JSON.stringify(value)}</span>;
  return <span>{String(value)}</span>;
}

export default function AIIntelligencePage() {
  const { hasPermission } = useHasPermission();
  const canGenerate = hasPermission(PERMISSIONS.AI.GENERATE);
  const [usage, setUsage] = useState<AIUsageStats | null>(null);
  const [usageError, setUsageError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState<SearchScope>('auto');
  const [searchResult, setSearchResult] = useState<CRMSearchResponse | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [emailPrompt, setEmailPrompt] = useState('');
  const [emailResult, setEmailResult] = useState<EmailGenerationResponse | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [isGeneratingEmail, setIsGeneratingEmail] = useState(false);

  useEffect(() => {
    let active = true;
    void aiService.getUsageStats()
      .then((result) => {
        if (active) setUsage(result);
      })
      .catch((error: unknown) => {
        if (active) setUsageError(getErrorMessage(error, 'AI usage is unavailable.'));
      });
    return () => {
      active = false;
    };
  }, []);

  const runSearch = async () => {
    if (!query.trim() || !canGenerate) return;
    setIsSearching(true);
    setSearchError(null);
    setSearchResult(null);
    try {
      setSearchResult(
        await aiService.searchCRM(query.trim(), scope === 'auto' ? undefined : scope),
      );
    } catch (error: unknown) {
      setSearchError(getErrorMessage(error, 'CRM search failed.'));
    } finally {
      setIsSearching(false);
    }
  };

  const handleSearch = (event: FormEvent) => {
    event.preventDefault();
    void runSearch();
  };

  const handleEmailGeneration = async (event: FormEvent) => {
    event.preventDefault();
    if (!emailPrompt.trim() || !canGenerate) return;
    setIsGeneratingEmail(true);
    setEmailError(null);
    setEmailResult(null);
    try {
      setEmailResult(await aiService.generateEmail(emailPrompt.trim()));
    } catch (error: unknown) {
      setEmailError(getErrorMessage(error, 'Email generation failed.'));
    } finally {
      setIsGeneratingEmail(false);
    }
  };

  const usageCards: Array<{ label: string; value: string | number; icon: LucideIcon }> = [
    { label: 'Requests this month', value: usage?.request_count ?? '—', icon: BarChart3 },
    { label: 'Tokens this month', value: usage?.tokens_used_this_month ?? '—', icon: Sparkles },
    {
      label: 'Estimated provider cost',
      value: usage ? `$${usage.estimated_cost_usd.toFixed(4)}` : '—',
      icon: Mail,
    },
  ];

  return (
    <main className="mx-auto max-w-[1500px] space-y-7 pb-14">
      <header className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white px-6 py-7 shadow-saas-sm sm:px-8">
        <div className="pointer-events-none absolute -right-20 -top-28 h-72 w-72 rounded-full bg-blue-100/60 blur-3xl" />
        <div className="relative flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.16em] text-blue-700">
              <Sparkles className="h-3.5 w-3.5" />
              Authorized AI
            </div>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
              AI Intelligence
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
              Search CRM records and create sales content using only data your role may access.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
              <CheckCircle2 className="h-4 w-4" />
            </span>
            Permission-aware workspace
          </div>
        </div>
      </header>

      <section className="grid gap-4 sm:grid-cols-3" aria-label="AI usage">
        {usageCards.map(({ label, value, icon: Icon }) => (
          <Card key={String(label)} className="relative overflow-hidden border-slate-200 bg-white p-5 shadow-saas-sm">
            <div className="flex items-start justify-between">
              <p className="text-xs font-medium text-slate-500">{label}</p>
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-50 text-blue-600">
                <Icon className="h-4 w-4" />
              </span>
            </div>
            <p className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">{value}</p>
            <div className="mt-4 h-1 w-12 rounded-full bg-blue-600" />
          </Card>
        ))}
      </section>
      {usageError && <p className="text-xs text-amber-700">{usageError}</p>}

      {!canGenerate && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <AlertCircle className="h-4 w-4 shrink-0" />
          Your role can view AI usage but cannot run AI operations.
        </div>
      )}

      <div className="grid items-start gap-5 xl:grid-cols-[1.08fr_0.92fr]">
        <Card className="overflow-hidden border-slate-200 bg-white shadow-saas-sm">
          <div className="border-b border-slate-100 px-6 py-5 sm:px-7">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                <Search className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-base font-semibold text-slate-950">Natural-language CRM search</h2>
                <p className="mt-1 text-xs leading-5 text-slate-500">Ask questions about the records you are authorized to see.</p>
              </div>
            </div>
          </div>
          <div className="space-y-5 p-6 sm:p-7">
            <form className="space-y-5" onSubmit={handleSearch}>
              <div className="space-y-2">
                <Label htmlFor="ai-search-scope" className="text-xs font-semibold text-slate-700">Record type</Label>
                <select
                  id="ai-search-scope"
                  value={scope}
                  onChange={(event) => setScope(event.target.value as SearchScope)}
                  className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50/60 px-3 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={!canGenerate || isSearching}
                >
                  <option value="auto">Auto-detect from question</option>
                  <option value="company">Companies</option>
                  <option value="lead">Leads</option>
                  <option value="contact">Contacts</option>
                  <option value="deal">Deals</option>
                  <option value="task">Tasks</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="ai-crm-query" className="text-xs font-semibold text-slate-700">Question</Label>
                <Input
                  id="ai-crm-query"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Show companies not contacted in 30 days with open deals above 500000"
                  className="h-11 rounded-xl border-slate-200 bg-slate-50/60 px-4 transition focus:bg-white"
                  disabled={!canGenerate || isSearching}
                />
              </div>
              <Button type="submit" className="h-11 rounded-xl px-5 shadow-sm" disabled={!canGenerate || isSearching || !query.trim()}>
                {isSearching && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Search authorized CRM data
              </Button>
            </form>
            {searchError && (
              <div className="flex flex-wrap items-center gap-3 rounded-xl border border-red-100 bg-red-50 px-4 py-3" role="alert">
                <p className="text-sm text-red-700">{searchError}</p>
                <Button type="button" variant="outline" size="sm" className="rounded-lg bg-white" disabled={isSearching} onClick={() => void runSearch()}>
                  Retry
                </Button>
              </div>
            )}
            {searchResult && (
              <div className="space-y-4 border-t border-slate-100 pt-5" aria-live="polite">
                <div className="flex items-start gap-2 text-sm text-slate-700">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                  <p>{searchResult.explanation}</p>
                </div>
                {searchResult.results.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">No matching records.</p>
                ) : (
                  <div className="space-y-3">
                    {searchResult.results.map((result, index) => (
                      <dl key={String(result.id ?? index)} className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 text-xs">
                        {Object.entries(result).map(([key, value]) => (
                          <div key={key} className="grid grid-cols-[minmax(7rem,9rem)_1fr] gap-3 py-1">
                            <dt className="font-medium capitalize text-slate-500">{key.replaceAll('_', ' ')}</dt>
                            <dd className="break-words text-slate-900"><ResultValue value={value} /></dd>
                          </div>
                        ))}
                      </dl>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>

        <Card className="overflow-hidden border-slate-200 bg-white shadow-saas-sm">
          <div className="border-b border-slate-100 px-6 py-5 sm:px-7">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-50 text-violet-600">
                <Mail className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-base font-semibold text-slate-950">Email intelligence</h2>
                <p className="mt-1 text-xs leading-5 text-slate-500">Create thoughtful, context-aware sales communication.</p>
              </div>
            </div>
          </div>
          <div className="space-y-5 p-6 sm:p-7">
            <form className="space-y-5" onSubmit={handleEmailGeneration}>
              <div className="space-y-2">
                <Label htmlFor="ai-email-prompt" className="text-xs font-semibold text-slate-700">Instructions and authorized context</Label>
                <Textarea
                  id="ai-email-prompt"
                  value={emailPrompt}
                  onChange={(event) => setEmailPrompt(event.target.value)}
                  placeholder="Draft a concise follow-up after a pricing discussion. Do not invent customer facts."
                  rows={7}
                  className="resize-none rounded-xl border-slate-200 bg-slate-50/60 px-4 py-3 transition focus:bg-white"
                  disabled={!canGenerate || isGeneratingEmail}
                />
              </div>
              <Button type="submit" className="h-11 rounded-xl bg-slate-950 px-5 shadow-sm hover:bg-slate-800" disabled={!canGenerate || isGeneratingEmail || !emailPrompt.trim()}>
                {isGeneratingEmail && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Generate email
              </Button>
            </form>
            {emailError && <p className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">{emailError}</p>}
            {emailResult && (
              <article className="space-y-4 rounded-2xl border border-violet-100 bg-gradient-to-br from-violet-50/70 to-blue-50/50 p-5" aria-live="polite">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider text-violet-600">Generated subject</p>
                  <p className="mt-1 text-base font-semibold text-slate-950">{emailResult.subject}</p>
                </div>
                <div className="border-t border-violet-100 pt-4">
                  <p className="whitespace-pre-wrap text-sm leading-6 text-slate-800">{emailResult.body}</p>
                </div>
                <div className="space-y-1 border-t border-violet-100 pt-4 text-xs leading-5 text-slate-600">
                  <p>{emailResult.rationale}</p>
                  {emailResult.suggested_send_time && <p>Suggested timing: {emailResult.suggested_send_time}</p>}
                </div>
              </article>
            )}
          </div>
        </Card>
      </div>
    </main>
  );
}
