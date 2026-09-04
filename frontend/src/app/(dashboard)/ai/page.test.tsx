import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AIIntelligencePage from './page';

const mocks = vi.hoisted(() => ({
  canRead: true,
  canGenerate: true,
  listConversations: vi.fn(),
  getConversation: vi.fn(),
  deleteConversation: vi.fn(),
  streamChatAssistant: vi.fn(),
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
  },
}));

describe('AIIntelligencePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.canRead = true;
    mocks.canGenerate = true;
    mocks.listConversations.mockResolvedValue([]);
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
            provider: 'openrouter',
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
      ),
    );
    expect(await screen.findByText('There are 4 open deals.')).toBeInTheDocument();
    expect(screen.getByText('Open deals')).toBeInTheDocument();
    expect(screen.getByText(/Fallback model used/)).toBeInTheDocument();
  });

  it('loads a tenant-scoped persisted conversation', async () => {
    mocks.listConversations.mockResolvedValue([{
      id: 'conversation-1',
      title: 'Pipeline review',
      model_name: 'model-a',
      created_at: '2026-09-04T00:00:00Z',
      updated_at: '2026-09-04T00:00:00Z',
    }]);
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
