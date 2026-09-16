import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AIChatAssistant } from './ai-chat-assistant';

const mocks = vi.hoisted(() => ({
  canGenerate: true,
  streamChatAssistant: vi.fn(),
  confirmAction: vi.fn(),
}));

vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({ hasPermission: () => mocks.canGenerate }),
}));

vi.mock('@/lib/api/ai', () => ({
  aiService: {
    streamChatAssistant: mocks.streamChatAssistant,
    confirmAction: mocks.confirmAction,
  },
}));

describe('AIChatAssistant', () => {
  beforeEach(() => {
    mocks.canGenerate = true;
    mocks.streamChatAssistant.mockReset();
    mocks.confirmAction.mockReset();
  });

  it('is not rendered without ai:generate permission', () => {
    mocks.canGenerate = false;

    render(<AIChatAssistant />);

    expect(screen.queryByRole('button', { name: 'Open AI Sales Assistant' })).toBeNull();
  });

  it('calls the real chat API and continues the server conversation', async () => {
    mocks.streamChatAssistant
      .mockResolvedValueOnce({
        conversation_id: 'conversation-1',
        response: 'Acme has one open deal.',
        evidence: [],
        proposed_actions: [],
      })
      .mockResolvedValueOnce({
        conversation_id: 'conversation-1',
        response: 'The deal is in Qualification.',
        evidence: [],
        proposed_actions: [],
      });
    render(<AIChatAssistant />);

    fireEvent.click(screen.getByRole('button', { name: 'Open AI Sales Assistant' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Message AI Sales Assistant' }), {
      target: { value: 'Find Acme' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('Acme has one open deal.')).toBeInTheDocument();
    expect(mocks.streamChatAssistant).toHaveBeenNthCalledWith(
      1,
      'Find Acme',
      undefined,
      expect.any(Object),
      expect.any(AbortSignal),
    );

    fireEvent.change(screen.getByRole('textbox', { name: 'Message AI Sales Assistant' }), {
      target: { value: 'Which stage?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(mocks.streamChatAssistant).toHaveBeenNthCalledWith(
        2,
        'Which stage?',
        'conversation-1',
        expect.any(Object),
        expect.any(AbortSignal),
      );
    });
  });

  it('shows provider failures without fabricating an answer', async () => {
    mocks.streamChatAssistant.mockRejectedValue(new Error('AI provider unavailable'));
    render(<AIChatAssistant />);

    fireEvent.click(screen.getByRole('button', { name: 'Open AI Sales Assistant' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Message AI Sales Assistant' }), {
      target: { value: 'Summarize pipeline' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('AI provider unavailable');
    expect(screen.queryByText(/pipeline is healthy/i)).toBeNull();
  });

  it('renders grounded database results, evidence, and follow-up questions', async () => {
    mocks.streamChatAssistant.mockResolvedValue({
      conversation_id: 'conversation-1',
      response: 'There are 7 companies.',
      evidence: [
        { entity_type: 'company', entity_id: 'company-1', label: 'Acme' },
      ],
      proposed_actions: [],
      result_blocks: [
        {
          key: 'company-count',
          title: 'Companies',
          entity_type: 'company',
          intent: 'count',
          results: [{ count: 7 }],
          result_count: 7,
          explanation: 'There are 7 matching company records.',
          generated_at: '2026-09-04T12:00:00Z',
        },
      ],
      follow_up_questions: ['Show the newest companies'],
    });
    render(<AIChatAssistant />);

    fireEvent.click(screen.getByRole('button', { name: 'Open AI Sales Assistant' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Message AI Sales Assistant' }), {
      target: { value: 'How many companies?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('There are 7 companies.')).toBeInTheDocument();
    expect(screen.getByText('There are 7 matching company records.')).toBeInTheDocument();
    expect(screen.getAllByText('7').length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: 'Acme' })).toHaveAttribute(
      'href',
      '/companies/company-1',
    );

    fireEvent.click(screen.getByRole('button', { name: 'Show the newest companies' }));
    await waitFor(() => {
      expect(mocks.streamChatAssistant).toHaveBeenLastCalledWith(
        'Show the newest companies',
        'conversation-1',
        expect.any(Object),
        expect.any(AbortSignal),
      );
    });
  });

  it('executes a task only after explicit confirmation', async () => {
    mocks.streamChatAssistant.mockResolvedValue({
      conversation_id: 'conversation-1',
      response: 'I prepared a task.',
      evidence: [],
      proposed_actions: [
        {
          action_type: 'create_task',
          title: 'Follow up with Acme',
          payload: {
            title: 'Follow up with Acme',
            description: 'Discuss renewal',
            due_date: '2026-09-18T09:00:00Z',
            priority: 'High',
            status: 'Pending',
            assigned_to: 'sales-user-1',
            lead_id: 'lead-1',
            contact_id: 'contact-1',
            company_id: 'company-1',
            deal_id: 'deal-1',
          },
          requires_confirmation: true,
          proposal_id: 'proposal-1',
        },
      ],
    });
    mocks.confirmAction.mockResolvedValue({
      proposal_id: 'proposal-1',
      action_type: 'create_task',
      status: 'executed',
      result: { id: 'task-1' },
    });
    render(<AIChatAssistant />);

    fireEvent.click(screen.getByRole('button', { name: 'Open AI Sales Assistant' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Message AI Sales Assistant' }), {
      target: { value: 'Create a follow-up task' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    const confirm = await screen.findByRole('button', { name: 'Confirm task' });
    expect(screen.getByText('Discuss renewal')).toBeInTheDocument();
    expect(screen.getByText('Task title')).toBeInTheDocument();
    expect(screen.getByText('Initial status')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('sales-user-1')).toBeInTheDocument();
    expect(screen.getByText('company-1')).toBeInTheDocument();
    expect(screen.getByText('deal-1')).toBeInTheDocument();
    expect(mocks.confirmAction).not.toHaveBeenCalled();
    fireEvent.click(confirm);

    await waitFor(() => expect(mocks.confirmAction).toHaveBeenCalledWith('proposal-1'));
    expect(await screen.findByRole('button', { name: 'Task created' })).toBeDisabled();
  });
});
