'use client';

import { useState } from 'react';
import Link from 'next/link';
import { GitBranch, Plus } from 'lucide-react';

import { ModalShell } from '@/components/common/modal-shell';
import { PermissionGate } from '@/components/common/permission-gate';
import { ResponsiveSelect } from '@/components/common/responsive-select';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useHasPermission } from '@/hooks/use-has-permission';
import {
  type DealItem,
  useCreateDealStageMutation,
  useDealStagesQuery,
  useKanbanBoardQuery,
  useUpdateDealStageMutation,
} from '@/lib/api/deals';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

function dealValue(deals: readonly DealItem[]): number {
  return deals.reduce((total, deal) => total + Number(deal.amount || 0), 0);
}

export default function PipelinesPage(): React.JSX.Element {
  const { hasPermission } = useHasPermission();
  const stagesQuery = useDealStagesQuery();
  const boardQuery = useKanbanBoardQuery();
  const createStage = useCreateDealStageMutation();
  const updateStage = useUpdateDealStageMutation();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [name, setName] = useState('');
  const [probability, setProbability] = useState(50);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const stages = stagesQuery.data ?? [];
  const board = boardQuery.data ?? {};
  const canUpdate = hasPermission(PERMISSIONS.DEALS.UPDATE);

  const submitStage = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setError('Stage name is required.');
      return;
    }
    try {
      await createStage.mutateAsync({ name: name.trim(), probability });
      setIsCreateOpen(false);
      setName('');
      setProbability(50);
      setError(null);
      setSuccess('Pipeline stage created successfully.');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Unable to create pipeline stage.'));
    }
  };

  const moveDeal = async (deal: DealItem, stage: string) => {
    setError(null);
    try {
      await updateStage.mutateAsync({ id: deal.id, stage });
      setSuccess(`“${deal.title}” moved to ${stage}.`);
    } catch (reason) {
      setError(getErrorMessage(reason, 'Unable to move deal.'));
    }
  };

  const isLoading = stagesQuery.isLoading || boardQuery.isLoading;
  const loadError = stagesQuery.error || boardQuery.error;

  return (
    <div className="space-y-6 pb-12">
      {(error || success) && (
        <div role="status" className={`rounded-xl border p-4 text-sm ${error ? 'border-rose-200 bg-rose-50 text-rose-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}>
          {error || success}
        </div>
      )}

      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
            <GitBranch className="size-7 text-blue-600" />
            Pipelines
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Track deal value and move opportunities through configured sales stages.
          </p>
        </div>
        <PermissionGate permission={PERMISSIONS.DEALS.PIPELINE}>
          <Button className="w-full gap-2 sm:w-auto" onClick={() => setIsCreateOpen(true)}>
            <Plus className="size-4" />
            Add Stage
          </Button>
        </PermissionGate>
      </div>

      {loadError && (
        <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {getErrorMessage(loadError, 'Unable to load the deal pipeline.')}
        </div>
      )}

      {!loadError && (isLoading ? (
        <div aria-label="Loading pipeline" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3].map((item) => <div key={item} className="h-64 animate-pulse rounded-xl border bg-slate-100" />)}
        </div>
      ) : (
        <div className="flex snap-x gap-4 overflow-x-auto pb-4">
          {stages.map((stage) => {
            const deals = board[stage.name] ?? [];
            return (
              <section key={stage.id} className="w-[85vw] max-w-sm shrink-0 snap-start rounded-xl border border-slate-200 bg-slate-50 p-3 sm:w-80" aria-labelledby={`stage-${stage.id}`}>
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <h2 id={`stage-${stage.id}`} className="font-semibold text-slate-900">{stage.name}</h2>
                    <p className="text-xs text-slate-500">{stage.probability}% probability</p>
                  </div>
                  <span className="rounded-full bg-white px-2 py-1 text-xs font-semibold text-slate-600 shadow-sm">{deals.length}</span>
                </div>
                <p className="mb-3 text-sm font-semibold text-slate-700">
                  {dealValue(deals).toLocaleString(undefined, { style: 'currency', currency: 'INR' })}
                </p>
                <div className="space-y-3">
                  {deals.length === 0 && <p className="rounded-lg border border-dashed p-4 text-center text-sm text-slate-500">No deals in this stage.</p>}
                  {deals.map((deal) => (
                    <article key={deal.id} className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
                      <Link href={`/deals/${deal.id}`} className="font-semibold text-slate-900 hover:text-blue-700 hover:underline">{deal.title}</Link>
                      <p className="mt-1 text-sm text-slate-600">{Number(deal.amount || 0).toLocaleString(undefined, { style: 'currency', currency: 'INR' })}</p>
                      {canUpdate && (
                        <div className="mt-3">
                          <ResponsiveSelect aria-label={`Move ${deal.title} to stage`} value={stage.name} disabled={updateStage.isPending} onValueChange={(value) => void moveDeal(deal, value)}>
                            {stages.map((option) => <option key={option.id} value={option.name}>{option.name}</option>)}
                          </ResponsiveSelect>
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      ))}

      <ModalShell isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} title="Add Pipeline Stage">
        <form onSubmit={submitStage} className="space-y-4">
          <div>
            <label htmlFor="stage-name" className="mb-1 block text-xs font-semibold">Stage name *</label>
            <Input id="stage-name" required maxLength={100} value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div>
            <label htmlFor="stage-probability" className="mb-1 block text-xs font-semibold">Default probability (%)</label>
            <Input id="stage-probability" required type="number" min="0" max="100" step="1" value={probability} onChange={(event) => setProbability(Number(event.target.value))} />
          </div>
          <div className="flex flex-col-reverse justify-end gap-2 border-t pt-4 sm:flex-row">
            <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={createStage.isPending}>{createStage.isPending ? 'Creating...' : 'Create Stage'}</Button>
          </div>
        </form>
      </ModalShell>
    </div>
  );
}
