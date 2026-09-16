import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AIIntelligencePage from './page';
import { setOrganizationContext } from '@/lib/organization-context';

const mocks = vi.hoisted(() => ({
  canRead: true,
  canGenerate: true,
  listConversations: vi.fn(),
  getConversation: vi.fn(),
  deleteConversation: vi.fn(),
  streamChatAssistant: vi.fn(),
  confirmAction: vi.fn(),
}));

vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({
    hasPermission: (permission: string) =>
      permission === 'ai:read' ? mocks.canRead : mocks.canGenerate,
  }),
}));

vi.mock('@/lib/api/ai', () => ({
  aiService: {
    listConversations: mocks.listConversations,
    getConversation: mocks.getConversation,
    deleteConversation: mocks.deleteConversation,
    streamChatAssistant: mocks.streamChatAssistant,
    confirmAction: mocks.confirmAction,
  },
}));

describe('AIIntelligencePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.canRead = true;
    mocks.canGenerate = true;
    mocks.listConversations.mockResolvedValue({ items: [], total: 0 });
    mocks.streamChatAssistant.mockImplementation(
      async (_question: string, _conversationId: string | undefined, handlers: { onDelta: (text: string) => void }) => {
        handlers.onDelta('There are 4 ');
        handlers.onDelta('open deals.');
        return {
          conversation_id: 'conversation-1',
          response: 'There are 4 open deals.',
          evidence: [],
          proposed_actions: [],
          result_blocks: [{
            key: 'deals',
            title: 'Open deals',
            entity_type: 'deal',
            intent: 'count',
            results: [{ count: 4 }],
            result_count: 4,
            explanation: 'There are 4 matching deal records.',
            generated_at: '2026-09-04T00:00:00Z',
          }],
          follow_up_questions: [],
          metadata: {
            model: 'model-b',
            provider: 'susanoox',
            fallback_used: true,
            attempted_model_count: 2,
            generated_at: '2026-09-04T00:00:00Z',
          },
        };
      },
    );
  });

  it('streams an authorized CRM answer and renders database results', async () => {
    render(<AIIntelligencePage />);
    fireEvent.change(screen.getByLabelText('Message CRM AI'), {
      target: { value: 'How many open deals are there?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() =>
      expect(mocks.streamChatAssistant).toHaveBeenCalledWith(
        'How many open deals are there?',
        undefined,
        expect.any(Object),
        expect.any(AbortSignal),
      ),
    );
    expect(await screen.findByText('There are 4 open deals.')).toBeInTheDocument();
    expect(screen.getByText('Open deals')).toBeInTheDocument();
    expect(screen.getByText(/Fallback model used/)).toBeInTheDocument();
  });

  it('renders every bounded deal row without exposing internal identifiers', async () => {
    const records = Array.from({ length: 50 }, (_, index) => ({
      id: `deal-${index}`,
      title: `Deal ${index}`,
      stage: 'Prospecting',
      organization_id: 'org-internal',
      custom_fields: { private_value: 'not-for-table' },
    }));
    mocks.streamChatAssistant.mockResolvedValue({
      conversation_id: 'conversation-1',
      response: 'Found 50 matching deal record(s).',
      result_blocks: [{
        key: 'deals', title: 'Deals', entity_type: 'deal', intent: 'list',
        results: records, result_count: 50,
        explanation: 'Found 50 matching deal record(s).',
        generated_at: '2026-09-16T00:00:00Z',
      }],
      evidence: [], proposed_actions: [], follow_up_questions: [],
    });
    render(<AIIntelligencePage />);
    fireEvent.change(screen.getByLabelText('Message CRM AI'), {
      target: { value: 'List all deals in a table' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('Deal 49')).toBeInTheDocument();
    expect(screen.getByText(/Showing the first 50 matching records/)).toBeInTheDocument();
    expect(screen.queryByText('deal-49')).not.toBeInTheDocument();
    expect(screen.queryByText('org-internal')).not.toBeInTheDocument();
    expect(screen.queryByText('not-for-table')).not.toBeInTheDocument();
  });

  it('loads a tenant-scoped persisted conversation', async () => {
    mocks.listConversations.mockResolvedValue({ items: [{
      id: 'conversation-1',
      title: 'Pipeline review',
      model_name: 'model-a',
      created_at: '2026-09-04T00:00:00Z',
      updated_at: '2026-09-04T00:00:00Z',
    }], total: 1 });
    mocks.getConversation.mockResolvedValue({
      id: 'conversation-1',
      title: 'Pipeline review',
      messages: [{
        id: 'prompt-1',
        user_prompt: 'Show pipeline',
        ai_response: 'Pipeline total is 500.',
        result_blocks: [],
        evidence: [],
        follow_up_questions: [],
        model: 'model-a',
        fallback_used: false,
        created_at: '2026-09-04T00:00:00Z',
      }],
    });
    render(<AIIntelligencePage />);

    fireEvent.click(await screen.findByRole('button', { name: /^Pipeline review/ }));
    expect(await screen.findByText('Show pipeline')).toBeInTheDocument();
    expect(screen.getByText('Pipeline total is 500.')).toBeInTheDocument();
  });

  it('cancels an active stream before opening history and ignores its late result', async () => {
    let completeStream: ((value: object) => void) | undefined;
    mocks.streamChatAssistant.mockImplementation(() => new Promise((resolve) => {
      completeStream = resolve;
    }));
    mocks.listConversations.mockResolvedValue({ items: [{
      id: 'history-1', title: 'Saved conversation', model_name: 'model-a',
      created_at: '2026-09-04T00:00:00Z', updated_at: '2026-09-04T00:00:00Z',
    }], total: 1 });
    mocks.getConversation.mockResolvedValue({ id: 'history-1', title: 'Saved conversation', messages: [{
      id: 'prompt-1', user_prompt: 'Saved question', ai_response: 'Saved answer',
      result_blocks: [], evidence: [], follow_up_questions: [],
      model: 'model-a', fallback_used: false, created_at: '2026-09-04T00:00:00Z',
    }] });
    render(<AIIntelligencePage />);
    fireEvent.change(screen.getByLabelText('Message CRM AI'), { target: { value: 'Live question' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    await waitFor(() => expect(mocks.streamChatAssistant).toHaveBeenCalled());
    const streamSignal = mocks.streamChatAssistant.mock.calls[0][3] as AbortSignal;
    fireEvent.click(await screen.findByRole('button', { name: /^Saved conversation/ }));
    expect(streamSignal.aborted).toBe(true);
    expect(await screen.findByText('Saved answer')).toBeInTheDocument();
    completeStream?.({ conversation_id: 'live-1', response: 'Late live answer',
      result_blocks: [], evidence: [], proposed_actions: [], follow_up_questions: [] });
    await waitFor(() => expect(screen.queryByText('Late live answer')).not.toBeInTheDocument());
    expect(screen.getByText('Saved answer')).toBeInTheDocument();
  });

  it('keeps the newly selected chat when an older conversation deletion completes late', async () => {
    let finishDelete: (() => void) | undefined;
    mocks.listConversations.mockResolvedValue({ items: [
      { id: 'chat-a', title: 'Conversation A', created_at: '2026-09-04T00:00:00Z', updated_at: '2026-09-04T00:00:00Z' },
      { id: 'chat-b', title: 'Conversation B', created_at: '2026-09-04T00:00:00Z', updated_at: '2026-09-04T00:00:00Z' },
    ], total: 2 });
    mocks.getConversation.mockImplementation(async (id: string) => ({
      id, title: id, messages: [{
        id: `${id}-prompt`, user_prompt: `Question ${id}`, ai_response: `Answer ${id}`,
        result_blocks: [], evidence: [], follow_up_questions: [],
        model: 'model-a', fallback_used: false, created_at: '2026-09-04T00:00:00Z',
      }],
    }));
    mocks.deleteConversation.mockImplementation(() => new Promise<void>((resolve) => {
      finishDelete = resolve;
    }));
    render(<AIIntelligencePage />);

    fireEvent.click(await screen.findByRole('button', { name: /^Conversation A/ }));
    expect(await screen.findByText('Answer chat-a')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Delete Conversation A' }));
    await waitFor(() => expect(mocks.deleteConversation).toHaveBeenCalledWith('chat-a'));
    fireEvent.click(screen.getByRole('button', { name: /^Conversation B/ }));
    expect(await screen.findByText('Answer chat-b')).toBeInTheDocument();

    finishDelete?.();
    await waitFor(() => expect(screen.queryByRole('button', { name: /^Conversation A/ })).not.toBeInTheDocument());
    expect(screen.getByText('Answer chat-b')).toBeInTheDocument();
  });

  it('does not apply an old organization history response after context switch', async () => {
    setOrganizationContext('org-a');
    let finishOld: ((value: object) => void) | undefined;
    mocks.listConversations.mockImplementationOnce(() => new Promise((resolve) => {
      finishOld = resolve;
    })).mockResolvedValue({ items: [], total: 0 });
    render(<AIIntelligencePage />);
    setOrganizationContext('org-b');
    finishOld?.({ items: [{ id: 'old-1', title: 'Old organization history' }], total: 1 });
    await waitFor(() => expect(mocks.listConversations).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('Old organization history')).not.toBeInTheDocument();
    setOrganizationContext(null);
  });

  it('shows retry without fabricating an answer when providers fail', async () => {
    mocks.streamChatAssistant.mockRejectedValue(new Error('All configured AI models are temporarily unavailable.'));
    render(<AIIntelligencePage />);
    fireEvent.change(screen.getByLabelText('Message CRM AI'), { target: { value: 'Show leads' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('All configured AI models are temporarily unavailable.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(screen.getByText('I could not complete that request.')).toBeInTheDocument();
  });

  it('disables chat generation without ai:generate', async () => {
    mocks.canGenerate = false;
    render(<AIIntelligencePage />);
    expect(screen.getByLabelText('Message CRM AI')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
    expect(mocks.streamChatAssistant).not.toHaveBeenCalled();
  });
});
