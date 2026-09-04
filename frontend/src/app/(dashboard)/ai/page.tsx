'use client';

import { FormEvent, useEffect, useState } from 'react';
import { AlertCircle, Loader2, Mail, Search, Sparkles } from 'lucide-react';

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

type SearchScope = 'lead' | 'contact' | 'company' | 'deal';

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
  const [scope, setScope] = useState<SearchScope>('company');
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
      setSearchResult(await aiService.searchCRM(query.trim(), scope));
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

  return (
    <main className="space-y-6 pb-12">
      <header>
        <div className="flex items-center gap-2 text-blue-700">
          <Sparkles className="h-5 w-5" />
          <span className="text-xs font-semibold uppercase tracking-wider">Authorized AI</span>
        </div>
        <h1 className="mt-2 text-2xl font-bold text-slate-950">AI Intelligence</h1>
        <p className="mt-1 text-sm text-slate-600">
          Search CRM records and create sales content using only data your role may access.
        </p>
      </header>

      <section className="grid gap-3 sm:grid-cols-3" aria-label="AI usage">
        <Card className="p-4">
          <p className="text-xs text-slate-500">Requests this month</p>
          <p className="mt-1 text-xl font-bold">{usage?.request_count ?? '—'}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-slate-500">Tokens this month</p>
          <p className="mt-1 text-xl font-bold">{usage?.tokens_used_this_month ?? '—'}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-slate-500">Estimated provider cost</p>
          <p className="mt-1 text-xl font-bold">
            {usage ? `$${usage.estimated_cost_usd.toFixed(4)}` : '—'}
          </p>
        </Card>
      </section>
      {usageError && <p className="text-xs text-amber-700">{usageError}</p>}

      {!canGenerate && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <AlertCircle className="h-4 w-4" /> Your role can view AI usage but cannot run AI operations.
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="space-y-4 p-5">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-blue-600" />
            <h2 className="font-semibold text-slate-950">Natural-language CRM search</h2>
          </div>
          <form className="space-y-4" onSubmit={handleSearch}>
            <div className="space-y-1.5">
              <Label htmlFor="ai-search-scope">Record type</Label>
              <select
                id="ai-search-scope"
                value={scope}
                onChange={(event) => setScope(event.target.value as SearchScope)}
                className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                disabled={!canGenerate || isSearching}
              >
                <option value="company">Companies</option>
                <option value="lead">Leads</option>
                <option value="contact">Contacts</option>
                <option value="deal">Deals</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ai-crm-query">Question</Label>
              <Input
                id="ai-crm-query"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Show companies not contacted in 30 days with open deals above 500000"
                disabled={!canGenerate || isSearching}
              />
            </div>
            <Button type="submit" disabled={!canGenerate || isSearching || !query.trim()}>
              {isSearching && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Search authorized CRM data
            </Button>
          </form>
          {searchError && (
            <div className="flex flex-wrap items-center gap-3" role="alert">
              <p className="text-sm text-red-700">{searchError}</p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={isSearching}
                onClick={() => void runSearch()}
              >
                Retry
              </Button>
            </div>
          )}
          {searchResult && (
            <div className="space-y-3" aria-live="polite">
              <p className="text-sm text-slate-700">{searchResult.explanation}</p>
              {searchResult.results.length === 0 ? (
                <p className="text-sm text-slate-500">No matching records.</p>
              ) : (
                <div className="space-y-2">
                  {searchResult.results.map((result, index) => (
                    <dl key={String(result.id ?? index)} className="rounded-lg border p-3 text-xs">
                      {Object.entries(result).map(([key, value]) => (
                        <div key={key} className="grid grid-cols-[9rem_1fr] gap-2 py-0.5">
                          <dt className="font-medium text-slate-500">{key.replaceAll('_', ' ')}</dt>
                          <dd className="break-words text-slate-900"><ResultValue value={value} /></dd>
                        </div>
                      ))}
                    </dl>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>

        <Card className="space-y-4 p-5">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-blue-600" />
            <h2 className="font-semibold text-slate-950">Email intelligence</h2>
          </div>
          <form className="space-y-4" onSubmit={handleEmailGeneration}>
            <div className="space-y-1.5">
              <Label htmlFor="ai-email-prompt">Instructions and authorized context</Label>
              <Textarea
                id="ai-email-prompt"
                value={emailPrompt}
                onChange={(event) => setEmailPrompt(event.target.value)}
                placeholder="Draft a concise follow-up after a pricing discussion. Do not invent customer facts."
                rows={6}
                disabled={!canGenerate || isGeneratingEmail}
              />
            </div>
            <Button
              type="submit"
              disabled={!canGenerate || isGeneratingEmail || !emailPrompt.trim()}
            >
              {isGeneratingEmail && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Generate email
            </Button>
          </form>
          {emailError && <p className="text-sm text-red-700">{emailError}</p>}
          {emailResult && (
            <article className="space-y-3 rounded-xl border border-blue-100 bg-blue-50/40 p-4" aria-live="polite">
              <div>
                <p className="text-xs font-medium text-slate-500">Subject</p>
                <p className="font-semibold text-slate-950">{emailResult.subject}</p>
              </div>
              <p className="whitespace-pre-wrap text-sm text-slate-800">{emailResult.body}</p>
              <p className="text-xs text-slate-600">{emailResult.rationale}</p>
              {emailResult.suggested_send_time && (
                <p className="text-xs text-slate-600">Suggested timing: {emailResult.suggested_send_time}</p>
              )}
            </article>
          )}
        </Card>
      </div>
    </main>
  );
}
