import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AIChatAssistant } from './ai-chat-assistant';

const mocks = vi.hoisted(() => ({
  canGenerate: true,
  chatAssistant: vi.fn(),
  confirmAction: vi.fn(),
}));

vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({ hasPermission: () => mocks.canGenerate }),
}));

vi.mock('@/lib/api/ai', () => ({
  aiService: { chatAssistant: mocks.chatAssistant, confirmAction: mocks.confirmAction },
}));

describe('AIChatAssistant', () => {
  beforeEach(() => {
    mocks.canGenerate = true;
    mocks.chatAssistant.mockReset();
    mocks.confirmAction.mockReset();
  });

  it('is not rendered without ai:generate permission', () => {
    mocks.canGenerate = false;

    render(<AIChatAssistant />);

    expect(screen.queryByRole('button', { name: 'Open AI Sales Assistant' })).toBeNull();
  });

  it('calls the real chat API and continues the server conversation', async () => {
    mocks.chatAssistant
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
    expect(mocks.chatAssistant).toHaveBeenNthCalledWith(1, 'Find Acme', undefined);

    fireEvent.change(screen.getByRole('textbox', { name: 'Message AI Sales Assistant' }), {
      target: { value: 'Which stage?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(mocks.chatAssistant).toHaveBeenNthCalledWith(
        2,
        'Which stage?',
        'conversation-1',
      );
    });
  });

  it('shows provider failures without fabricating an answer', async () => {
    mocks.chatAssistant.mockRejectedValue(new Error('AI provider unavailable'));
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
    mocks.chatAssistant.mockResolvedValue({
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
      expect(mocks.chatAssistant).toHaveBeenLastCalledWith(
        'Show the newest companies',
        'conversation-1',
      );
    });
  });

  it('executes a task only after explicit confirmation', async () => {
    mocks.chatAssistant.mockResolvedValue({
      conversation_id: 'conversation-1',
      response: 'I prepared a task.',
      evidence: [],
      proposed_actions: [
        {
          action_type: 'create_task',
          title: 'Follow up with Acme',
          payload: { title: 'Follow up with Acme' },
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
    expect(mocks.confirmAction).not.toHaveBeenCalled();
    fireEvent.click(confirm);

    await waitFor(() => expect(mocks.confirmAction).toHaveBeenCalledWith('proposal-1'));
    expect(await screen.findByRole('button', { name: 'Task created' })).toBeDisabled();
  });
});
