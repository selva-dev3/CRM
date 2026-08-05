'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Briefcase,
  Trophy,
  XCircle,
  Sparkles,
  Copy,
  User,
  DollarSign,
  Edit,
  Trash2,
  FileText,
  Package,
  History,
  Calculator,
  Plus,
  CheckCircle2,
  AlertCircle,
  Calendar,
  X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { ConfirmModal } from '@/components/shared/confirm-modal';
import {
  useDealQuery,
  useUpdateDealMutation,
  useDeleteDealMutation,
  useMarkDealWonMutation,
  useMarkDealLostMutation,
  getDealProductsApi,
  addDealProductApi,
  removeDealProductApi,
  getDealTimelineApi,
  getDealNotesApi,
  addDealNoteApi,
  getDealQuotesApi,
  predictDealWinRateApi,
  cloneDealApi,
  getDealCommissionApi
} from '@/lib/api/deals';
import { useUsersQuery } from '@/lib/api/users';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const STAGES = ['Prospecting', 'Qualification', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost'];

export default function DealDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();

  const dealId = (params.id as string) || '';

  const [activeTab, setActiveTab] = useState<'products' | 'timeline' | 'notes' | 'quotes' | 'commission'>('products');
  const [newNoteContent, setNewNoteContent] = useState('');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modals
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [aiPrediction, setAiPrediction] = useState<any>(null);

  // Edit Form State
  const [formTitle, setFormTitle] = useState('');
  const [formAmount, setFormAmount] = useState<number | ''>('');
  const [formStage, setFormStage] = useState('Prospecting');
  const [formProbability, setFormProbability] = useState<number | ''>(10);
  const [formAssignedTo, setFormAssignedTo] = useState('');

  // Main Deal Query
  const { data: deal, isLoading, isError, refetch } = useDealQuery(dealId);
  const { data: users = [] } = useUsersQuery();

  // Sub-resource queries
  const { data: products = [], refetch: refetchProducts } = useQuery({
    queryKey: ['deal-products', dealId],
    queryFn: () => getDealProductsApi(dealId),
    enabled: !!dealId,
  });

  const { data: timeline = [] } = useQuery({
    queryKey: ['deal-timeline', dealId],
    queryFn: () => getDealTimelineApi(dealId),
    enabled: !!dealId,
  });

  const { data: notes = [], refetch: refetchNotes } = useQuery({
    queryKey: ['deal-notes', dealId],
    queryFn: () => getDealNotesApi(dealId),
    enabled: !!dealId,
  });

  const { data: quotes = [] } = useQuery({
    queryKey: ['deal-quotes', dealId],
    queryFn: () => getDealQuotesApi(dealId),
    enabled: !!dealId,
  });

  const { data: commission } = useQuery({
    queryKey: ['deal-commission', dealId],
    queryFn: () => getDealCommissionApi(dealId),
    enabled: !!dealId,
  });

  // Mutations
  const updateDealMutation = useUpdateDealMutation();
  const deleteDealMutation = useDeleteDealMutation();
  const markWonMutation = useMarkDealWonMutation();
  const markLostMutation = useMarkDealLostMutation();

  const addNoteMutation = useMutation({
    mutationFn: (content: string) => addDealNoteApi({ id: dealId, content }),
    onSuccess: () => {
      setSuccessMessage('Deal note added successfully.');
      setNewNoteContent('');
      refetchNotes();
      queryClient.invalidateQueries({ queryKey: ['deal-notes', dealId] });
    },
    onError: () => {
      setErrorMessage('Failed to add note.');
    },
  });

  const openEditModal = () => {
    if (!deal) return;
    setFormTitle(deal.title || '');
    setFormAmount(deal.amount || '');
    setFormStage(deal.stage || 'Prospecting');
    setFormProbability(deal.probability ?? 10);
    setFormAssignedTo(deal.assigned_to || '');
    setIsEditModalOpen(true);
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dealId) return;
    try {
      setErrorMessage(null);
      await updateDealMutation.mutateAsync({
        id: dealId,
        data: {
          title: formTitle,
          amount: Number(formAmount) || 0,
          stage: formStage,
          probability: formProbability !== '' ? Number(formProbability) : undefined,
          assigned_to: formAssignedTo || undefined,
        },
      });
      setSuccessMessage('Deal details updated successfully.');
      setIsEditModalOpen(false);
      refetch();
    } catch {
      setErrorMessage('Failed to update deal.');
    }
  };

  const handleConfirmDelete = async () => {
    try {
      setErrorMessage(null);
      await deleteDealMutation.mutateAsync(dealId);
      router.push('/deals');
    } catch {
      setErrorMessage('Failed to delete deal.');
      setIsDeleteModalOpen(false);
    }
  };

  const handleMarkWon = async () => {
    if (!deal) return;
    try {
      setErrorMessage(null);
      await markWonMutation.mutateAsync({ id: dealId, final_amount: deal.amount });
      setSuccessMessage(`Deal '${deal.title}' marked as Closed Won! 🎉`);
      refetch();
    } catch {
      setErrorMessage('Failed to mark deal as won.');
    }
  };

  const handleMarkLost = async () => {
    if (!deal) return;
    try {
      setErrorMessage(null);
      await markLostMutation.mutateAsync({ id: dealId, reason: 'Budget constraints' });
      setSuccessMessage(`Deal '${deal.title}' marked as Closed Lost.`);
      refetch();
    } catch {
      setErrorMessage('Failed to mark deal as lost.');
    }
  };

  const handlePredictWinRate = async () => {
    try {
      setErrorMessage(null);
      const res = await predictDealWinRateApi(dealId);
      setAiPrediction(res);
      setSuccessMessage(`AI Prediction generated: ${res.predicted_probability || deal?.probability}% win probability.`);
    } catch {
      setErrorMessage('Failed to generate AI win rate prediction.');
    }
  };

  const handleCloneDeal = async () => {
    if (!deal) return;
    try {
      setErrorMessage(null);
      const cloned = await cloneDealApi({ id: dealId, new_title: `${deal.title} (Copy)` });
      setSuccessMessage(`Cloned deal '${cloned.title}' successfully.`);
      router.push(`/deals/${cloned.id}`);
    } catch {
      setErrorMessage('Failed to clone deal.');
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 text-center text-xs font-semibold text-slate-500">
        Loading deal details...
      </div>
    );
  }

  if (isError || !deal) {
    return (
      <div className="space-y-4 p-6">
        <Link href="/deals" className="inline-flex items-center text-xs font-bold text-blue-600 hover:underline gap-1">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Sales Deals
        </Link>
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-900 text-xs font-medium">
          Sales deal not found or an error occurred.
        </div>
      </div>
    );
  }

  const assignedUser = users.find((u) => u.id === deal.assigned_to);

  return (
    <div className="space-y-6">
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <Link href="/deals" className="inline-flex items-center text-xs font-bold text-slate-500 hover:text-blue-600 transition gap-1 mb-2">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Sales Deals
          </Link>
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center text-white font-black text-xl shadow-md">
              <Briefcase className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">{deal.title}</h1>
              <p className="text-xs font-medium text-slate-500 flex items-center gap-2 mt-0.5">
                <span>Stage: {deal.stage}</span>
                <span>&bull;</span>
                <span className="font-bold text-blue-700">${deal.amount ? deal.amount.toLocaleString() : '0'}</span>
              </p>
            </div>
          </div>
        </div>

        {/* Action Header Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            size="sm"
            onClick={handleMarkWon}
            className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs gap-1.5 cursor-pointer"
          >
            <Trophy className="w-3.5 h-3.5" />
            <span>Mark Won</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={handleMarkLost}
            className="border-rose-300 text-rose-600 hover:bg-rose-50 font-semibold text-xs gap-1.5 cursor-pointer"
          >
            <XCircle className="w-3.5 h-3.5" />
            <span>Mark Lost</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={handlePredictWinRate}
            className="border-indigo-300 text-indigo-700 bg-indigo-50 hover:bg-indigo-100 font-semibold text-xs gap-1.5 cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
            <span>AI Predict</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={handleCloneDeal}
            className="border-slate-300 font-semibold text-xs gap-1.5 cursor-pointer"
          >
            <Copy className="w-3.5 h-3.5 text-indigo-600" />
            <span>Clone</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={openEditModal}
            className="border-slate-300 font-semibold text-xs gap-1.5 cursor-pointer"
          >
            <Edit className="w-3.5 h-3.5 text-blue-600" />
            <span>Edit</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => setIsDeleteModalOpen(true)}
            className="border-rose-300 text-rose-600 hover:bg-rose-50 font-semibold text-xs gap-1.5 cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Delete</span>
          </Button>
        </div>
      </div>

      {/* Feedback Notifications */}
      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs font-medium flex items-center gap-2 animate-in fade-in-50">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs font-medium flex items-center gap-2 animate-in fade-in-50">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* AI Win Probability Card if generated */}
      {aiPrediction && (
        <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-2xl space-y-2 text-indigo-950 animate-in fade-in-50">
          <div className="flex items-center gap-2 font-bold text-xs">
            <Sparkles className="w-4 h-4 text-indigo-600" />
            <span>AI Sales Assistant - Win Rate Forecast</span>
          </div>
          <p className="text-xs">
            Predicted Win Probability: <strong className="text-indigo-700">{aiPrediction.predicted_probability}%</strong>
          </p>
          {aiPrediction.key_drivers && (
            <div className="text-[11px] text-indigo-800 font-medium">
              Key Drivers: {aiPrediction.key_drivers.join(', ')}
            </div>
          )}
        </div>
      )}

      {/* Profile Overview Card */}
      <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-4">
        <h2 className="text-sm font-bold text-slate-900">Deal Metrics</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
            <span className="text-slate-400 font-medium flex items-center gap-1">
              <DollarSign className="w-3.5 h-3.5 text-blue-600" /> Total Deal Value
            </span>
            <span className="font-extrabold text-blue-700 text-sm">
              ${deal.amount ? deal.amount.toLocaleString() : '0'}
            </span>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
            <span className="text-slate-400 font-medium flex items-center gap-1">
              <Briefcase className="w-3.5 h-3.5 text-slate-500" /> Pipeline Stage
            </span>
            <span className="font-bold text-slate-900">{deal.stage}</span>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
            <span className="text-slate-400 font-medium flex items-center gap-1">
              <Trophy className="w-3.5 h-3.5 text-amber-500" /> Win Probability
            </span>
            <span className="font-bold text-slate-900">{deal.probability ?? 10}%</span>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
            <span className="text-slate-400 font-medium flex items-center gap-1">
              <User className="w-3.5 h-3.5 text-indigo-500" /> Assigned Rep
            </span>
            <span className="font-bold text-slate-900">
              {assignedUser ? assignedUser.name || assignedUser.email : deal.assigned_to || 'Unassigned'}
            </span>
          </div>
        </div>
      </div>

      {/* Sub-Resource Navigation Tabs */}
      <div className="flex items-center border-b border-slate-200 gap-6 text-sm font-semibold text-slate-600 overflow-x-auto">
        <button
          onClick={() => setActiveTab('products')}
          className={`pb-3 cursor-pointer transition border-b-2 flex items-center gap-2 whitespace-nowrap ${
            activeTab === 'products' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Package className="w-4 h-4" />
          <span>Products ({products.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('timeline')}
          className={`pb-3 cursor-pointer transition border-b-2 flex items-center gap-2 whitespace-nowrap ${
            activeTab === 'timeline' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <History className="w-4 h-4" />
          <span>Stage History</span>
        </button>

        <button
          onClick={() => setActiveTab('notes')}
          className={`pb-3 cursor-pointer transition border-b-2 flex items-center gap-2 whitespace-nowrap ${
            activeTab === 'notes' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Notes ({notes.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('quotes')}
          className={`pb-3 cursor-pointer transition border-b-2 flex items-center gap-2 whitespace-nowrap ${
            activeTab === 'quotes' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <DollarSign className="w-4 h-4" />
          <span>Quotes ({quotes.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('commission')}
          className={`pb-3 cursor-pointer transition border-b-2 flex items-center gap-2 whitespace-nowrap ${
            activeTab === 'commission' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Calculator className="w-4 h-4" />
          <span>Rep Commission Split</span>
        </button>
      </div>

      {/* TAB CONTENT: Products */}
      {activeTab === 'products' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Line Items & Products</h2>
          {products.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No product items added to this deal yet.
            </div>
          ) : (
            <div className="space-y-2">
              {products.map((prod: any, idx: number) => (
                <div key={idx} className="p-4 bg-white rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <Package className="w-4 h-4 text-blue-600" />
                    <div>
                      <div className="font-bold text-slate-900">{prod.name || `Product #${prod.id}`}</div>
                      <div className="text-slate-500 text-[11px]">SKU: {prod.sku || 'N/A'}</div>
                    </div>
                  </div>
                  <div className="text-right font-bold text-blue-700 text-sm">
                    ${prod.unit_price ? prod.unit_price.toLocaleString() : '0'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Stage History Timeline */}
      {activeTab === 'timeline' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Stage Migration History</h2>
          {timeline.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              Initial deal stage set to <strong className="text-slate-900">{deal.stage}</strong>.
            </div>
          ) : (
            <div className="space-y-2">
              {timeline.map((evt: any, idx: number) => (
                <div key={idx} className="p-3 bg-white rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-slate-900">{evt.stage_name || 'Stage Updated'}</div>
                    <div className="text-slate-500 text-[11px]">{evt.description || 'Moved stage'}</div>
                  </div>
                  <span className="text-[11px] text-slate-400">{evt.created_at || 'Just now'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Notes */}
      {activeTab === 'notes' && (
        <div className="space-y-4">
          <div className="p-4 bg-white rounded-2xl border border-slate-200 space-y-3">
            <Label className="font-semibold text-slate-700 text-xs">Add New Deal Note</Label>
            <Input
              type="text"
              placeholder="Type deal notes, negotiation terms, or client requirements..."
              value={newNoteContent}
              onChange={(e) => setNewNoteContent(e.target.value)}
              className="h-9 text-xs"
            />
            <div className="flex justify-end">
              <Button
                size="sm"
                onClick={() => addNoteMutation.mutate(newNoteContent)}
                disabled={!newNoteContent.trim() || addNoteMutation.isPending}
                className="bg-blue-600 text-white font-semibold text-xs gap-1 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>Add Note</span>
              </Button>
            </div>
          </div>

          <h2 className="text-sm font-bold text-slate-900 pt-2">Saved Deal Notes</h2>
          {notes.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No notes logged for this deal yet. Add your first note above.
            </div>
          ) : (
            <div className="space-y-2">
              {notes.map((note: any, idx: number) => (
                <div key={idx} className="p-4 bg-white rounded-xl border border-slate-200 text-xs space-y-1">
                  <div className="font-medium text-slate-900">{note.content}</div>
                  <div className="text-[10px] text-slate-400">{note.created_at || 'Saved'}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Quotes */}
      {activeTab === 'quotes' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Generated Price Quotes</h2>
          {quotes.length === 0 ? (
            <div className="p-6 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
              No price quotes generated for this deal yet.
            </div>
          ) : (
            <div className="space-y-2">
              {quotes.map((quote: any, idx: number) => (
                <div key={idx} className="p-4 bg-white rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                  <div>
                    <div className="font-bold text-slate-900">{quote.title || `Quote #${quote.id}`}</div>
                    <div className="text-slate-500 text-[11px] font-medium">Status: {quote.status || 'Draft'}</div>
                  </div>
                  <div className="text-right font-bold text-emerald-700 text-sm">
                    ${quote.total_amount ? quote.total_amount.toLocaleString() : '0'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Sales Commission Calculation */}
      {activeTab === 'commission' && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900">Sales Representative Commission Split</h2>
          <div className="p-6 bg-white rounded-2xl border border-slate-200 text-xs space-y-3">
            <div className="flex items-center gap-2 font-bold text-slate-900 text-sm">
              <Calculator className="w-5 h-5 text-blue-600" />
              <span>Calculated Rep Commission</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-400 font-medium">Commission Rate</span>
                <div className="font-bold text-slate-900 text-base">{commission?.commission_rate_pct || 10}%</div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-400 font-medium">Deal Amount</span>
                <div className="font-bold text-slate-900 text-base">${deal.amount ? deal.amount.toLocaleString() : '0'}</div>
              </div>

              <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-100">
                <span className="text-emerald-700 font-medium">Estimated Payout</span>
                <div className="font-black text-emerald-800 text-base">
                  ${commission?.estimated_commission ? commission.estimated_commission.toLocaleString() : ((deal.amount || 0) * 0.1).toLocaleString()}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* EDIT DEAL MODAL */}
      {isEditModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-md bg-white rounded-2xl border border-slate-300 shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <Edit className="w-5 h-5 text-blue-600" />
                <span>Edit Sales Deal</span>
              </h3>
              <button type="button" onClick={() => setIsEditModalOpen(false)} className="text-slate-400 hover:text-slate-700 cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="space-y-4 text-xs">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Deal Title</Label>
                <Input
                  type="text"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Amount ($)</Label>
                  <Input
                    type="number"
                    value={formAmount}
                    onChange={(e) => setFormAmount(e.target.value !== '' ? Number(e.target.value) : '')}
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Pipeline Stage</Label>
                  <select
                    value={formStage}
                    onChange={(e) => setFormStage(e.target.value)}
                    className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                  >
                    {STAGES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Win Probability (%)</Label>
                  <Input
                    type="number"
                    value={formProbability}
                    onChange={(e) => setFormProbability(e.target.value !== '' ? Number(e.target.value) : '')}
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1">
                  <Label className="font-semibold text-slate-700">Assigned Sales Rep</Label>
                  <select
                    value={formAssignedTo}
                    onChange={(e) => setFormAssignedTo(e.target.value)}
                    className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                  >
                    <option value="">-- Select Sales Rep --</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name || u.email} ({u.email})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setIsEditModalOpen(false)} className="cursor-pointer">
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={updateDealMutation.isPending} className="bg-blue-600 text-white font-semibold cursor-pointer">
                  {updateDealMutation.isPending ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DELETE CONFIRM MODAL */}
      <ConfirmModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onConfirm={handleConfirmDelete}
        title="Delete Sales Deal"
        description="This action cannot be undone."
        confirmText="Delete Deal"
        variant="danger"
        isLoading={deleteDealMutation.isPending}
        message={
          <p>
            Are you sure you want to delete deal <strong className="text-slate-900">{deal.title}</strong>?
          </p>
        }
      />
    </div>
  );
}
