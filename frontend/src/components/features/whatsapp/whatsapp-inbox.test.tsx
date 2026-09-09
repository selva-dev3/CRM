import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  permissions: new Set<string>(),
  params: new URLSearchParams(),
  replace: vi.fn(),
  action: vi.fn(),
  send: vi.fn(),
  sendTemplate: vi.fn(),
  retryMessage: vi.fn(),
  list: vi.fn(),
  detail: vi.fn(),
  messages: vi.fn(),
  templates: vi.fn(),
  assignees: vi.fn(),
  identityAction: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace }),
  useSearchParams: () => mocks.params,
}));

vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({
    hasPermission: (permission: string) => mocks.permissions.has(permission),
    hasAnyPermission: (permissions: string[]) => permissions.some((item) => mocks.permissions.has(item)),
  }),
}));

vi.mock('@/lib/api/whatsapp', () => ({
  useWhatsAppConversations: (...args: unknown[]) => mocks.list(...args),
  useWhatsAppConversation: (...args: unknown[]) => mocks.detail(...args),
  useWhatsAppMessages: (...args: unknown[]) => mocks.messages(...args),
  useWhatsAppScope: () => 'user-a:org-a',
  useWhatsAppTemplates: (...args: unknown[]) => mocks.templates(...args),
  useWhatsAppAssignees: (...args: unknown[]) => mocks.assignees(...args),
  useWhatsAppSend: () => ({ mutateAsync: mocks.send, isPending: false }),
  useWhatsAppSendTemplate: () => ({ mutateAsync: mocks.sendTemplate, isPending: false }),
  useWhatsAppRetryMessage: () => ({ mutateAsync: mocks.retryMessage, isPending: false }),
  useWhatsAppConversationAction: () => ({ mutateAsync: mocks.action, isPending: false }),
  useWhatsAppIdentityAction: () => ({ mutateAsync: mocks.identityAction, isPending: false }),
}));

import { PERMISSIONS } from '@/lib/permissions';
import { WhatsAppInbox } from './whatsapp-inbox';

const conversation = {
  id: 'conversation-a',
  identity_id: 'identity-a',
  status: 'OPEN',
  ai_enabled: true,
  assigned_user_id: 'agent-a',
  last_customer_message_at: new Date(Date.now() - 60_000).toISOString(),
  last_message_at: new Date().toISOString(),
  customer_phone: '+14155552671',
  identity_state: 'MATCHED_CONTACT',
  consent: 'UNKNOWN',
  contact_id: 'contact-a',
  lead_id: null,
  unread_count: 2,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.permissions.clear();
  mocks.params = new URLSearchParams();
  mocks.list.mockReturnValue({ data: [], isLoading: false, isError: false });
  mocks.detail.mockReturnValue({ data: undefined, isLoading: false, isError: false });
  mocks.messages.mockReturnValue({ data: [], isLoading: false, isError: false });
  mocks.templates.mockReturnValue({ data: [], isLoading: false, isError: false });
  mocks.assignees.mockReturnValue({ data: [], isLoading: false, isError: false });
  mocks.action.mockResolvedValue({});
  mocks.identityAction.mockResolvedValue({});
  mocks.send.mockResolvedValue({});
  mocks.sendTemplate.mockResolvedValue({});
  mocks.retryMessage.mockResolvedValue({});
});

describe('WhatsAppInbox', () => {
  it('hides manual retry during automatic backoff', () => {
    mocks.permissions.add(PERMISSIONS.WHATSAPP.READ_ALL);
    mocks.permissions.add(PERMISSIONS.WHATSAPP.SEND);
    mocks.params = new URLSearchParams('conversation=conversation-a');
    mocks.detail.mockReturnValue({ data: conversation, isLoading: false, isError: false });
    mocks.messages.mockReturnValue({ data: [{
      id: 'pending-message', direction: 'OUTBOUND', source: 'HUMAN', message_type: 'text',
      body: 'Waiting for automatic retry', status: 'PENDING', retryable: false,
      error_code: 'WHATSAPP_PROVIDER_RATE_LIMITED', error_message: null, media_available: false,
    }], isLoading: false, isError: false });
    render(<WhatsAppInbox />);
    expect(screen.getByText('Waiting for automatic retry')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry safely' })).not.toBeInTheDocument();
  });
  it('enforces the permission gate and does not enable data access', () => {
    render(<WhatsAppInbox />);

    expect(screen.getByText('You do not have access to WhatsApp conversations.')).toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledWith('', 0, false);
  });

  it('shows loading, error, and empty conversation states', () => {
    mocks.permissions.add(PERMISSIONS.WHATSAPP.READ_ALL);
    const { rerender } = render(<WhatsAppInbox />);
    expect(screen.getByText('No conversations found.')).toBeInTheDocument();

    mocks.list.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    rerender(<WhatsAppInbox />);
    expect(screen.getByLabelText('Loading conversations')).toBeInTheDocument();

    mocks.list.mockReturnValue({ data: undefined, isLoading: false, isError: true, error: new Error('Unavailable') });
    rerender(<WhatsAppInbox />);
    expect(screen.getByRole('alert')).toHaveTextContent('Unavailable');
  });

  it('renders unread/status data and performs send, assignment, AI, and takeover actions', async () => {
    mocks.permissions.add(PERMISSIONS.WHATSAPP.READ_ALL);
    mocks.permissions.add(PERMISSIONS.WHATSAPP.SEND);
    mocks.permissions.add(PERMISSIONS.WHATSAPP.ASSIGN);
    mocks.permissions.add(PERMISSIONS.WHATSAPP.MANAGE_AI);
    mocks.permissions.add(PERMISSIONS.WHATSAPP.TAKEOVER);
    mocks.params = new URLSearchParams('conversation=conversation-a');
    mocks.list.mockReturnValue({ data: [conversation], isLoading: false, isError: false });
    mocks.detail.mockReturnValue({ data: conversation, isLoading: false, isError: false });
    mocks.messages.mockReturnValue({
      data: [{
        id: 'message-a', direction: 'OUTBOUND', source: 'AI', message_type: 'text', body: 'Hello',
        status: 'FAILED', retryable: true, error_code: 'WHATSAPP_PROVIDER_RATE_LIMITED', error_message: 'WhatsApp temporarily rate limited the request.',
        media_available: false, created_at: new Date().toISOString(), provider_timestamp: null,
        sent_at: null, delivered_at: null, read_at: null,
      }],
      isLoading: false,
      isError: false,
    });
    mocks.assignees.mockReturnValue({ data: [{ id: 'agent-a', name: 'Agent A' }, { id: 'agent-b', name: 'Agent B' }], isLoading: false, isError: false });
    const user = userEvent.setup();

    render(<WhatsAppInbox />);

    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('AI · FAILED')).toBeInTheDocument();
    expect(screen.getByText('WhatsApp temporarily rate limited the request.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry safely' }));
    fireEvent.change(screen.getByLabelText('Assigned agent'), { target: { value: 'agent-b' } });
    await user.click(screen.getByRole('button', { name: 'Disable AI' }));
    await user.click(screen.getByRole('button', { name: 'Take over' }));
    await waitFor(() => expect(screen.getByLabelText('WhatsApp message')).toBeInTheDocument());
    await user.type(screen.getByLabelText('WhatsApp message'), 'A human reply');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(mocks.action).toHaveBeenCalledWith({ type: 'update', payload: { assigned_user_id: 'agent-b' } });
    expect(mocks.action).toHaveBeenCalledWith({ type: 'update', payload: { ai_enabled: false } });
    expect(mocks.action).toHaveBeenCalledWith({ type: 'takeover' });
    expect(mocks.send).toHaveBeenCalledWith(expect.objectContaining({ body: 'A human reply' }));
    expect(mocks.retryMessage).toHaveBeenCalledWith('message-a');
  });

  it('reuses the idempotency key when an accepted send response is lost', async () => {
    mocks.permissions.add(PERMISSIONS.WHATSAPP.READ_ALL);
    mocks.permissions.add(PERMISSIONS.WHATSAPP.SEND);
    mocks.params = new URLSearchParams('conversation=conversation-a');
    mocks.detail.mockReturnValue({ data: conversation, isLoading: false, isError: false });
    mocks.send.mockRejectedValueOnce(new Error('Response lost')).mockResolvedValueOnce({});
    const user = userEvent.setup();
    render(<WhatsAppInbox />);

    await waitFor(() => expect(screen.getByLabelText('WhatsApp message')).toBeInTheDocument());
    await user.type(screen.getByLabelText('WhatsApp message'), 'Please confirm');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(mocks.send).toHaveBeenCalledTimes(2);
    expect(mocks.send.mock.calls[0][0].idempotency_key).toBe(
      mocks.send.mock.calls[1][0].idempotency_key
    );
  });

  it('keeps drafts and unresolved idempotency keys isolated by conversation', async () => {
    mocks.permissions.add(PERMISSIONS.WHATSAPP.READ_ALL);
    mocks.permissions.add(PERMISSIONS.WHATSAPP.SEND);
    mocks.params = new URLSearchParams('conversation=conversation-a');
    mocks.detail.mockReturnValue({ data: conversation, isLoading: false, isError: false });
    mocks.send
      .mockRejectedValueOnce(new Error('Response lost for A'))
      .mockRejectedValueOnce(new Error('Response lost for B'))
      .mockResolvedValueOnce({});
    const user = userEvent.setup();
    const { rerender } = render(<WhatsAppInbox />);

    await waitFor(() => expect(screen.getByLabelText('WhatsApp message')).toBeInTheDocument());
    await user.type(screen.getByLabelText('WhatsApp message'), 'Same body');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    mocks.params = new URLSearchParams('conversation=conversation-b');
    rerender(<WhatsAppInbox />);
    await waitFor(() => expect(screen.getByLabelText('WhatsApp message')).toHaveValue(''));
    await user.type(screen.getByLabelText('WhatsApp message'), 'Same body');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    mocks.params = new URLSearchParams('conversation=conversation-a');
    rerender(<WhatsAppInbox />);
    await waitFor(() => expect(screen.getByLabelText('WhatsApp message')).toHaveValue('Same body'));
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(mocks.send.mock.calls[0][0].idempotency_key).not.toBe(
      mocks.send.mock.calls[1][0].idempotency_key
    );
    expect(mocks.send.mock.calls[0][0].idempotency_key).toBe(
      mocks.send.mock.calls[2][0].idempotency_key
    );
  });

  it('retains separate unresolved keys for different request fingerprints', async () => {
    mocks.permissions.add(PERMISSIONS.WHATSAPP.READ_ALL);
    mocks.permissions.add(PERMISSIONS.WHATSAPP.SEND);
    mocks.params = new URLSearchParams('conversation=conversation-a');
    mocks.detail.mockReturnValue({ data: conversation, isLoading: false, isError: false });
    mocks.send
      .mockRejectedValueOnce(new Error('First response lost'))
      .mockRejectedValueOnce(new Error('Second response lost'))
      .mockResolvedValueOnce({});
    const user = userEvent.setup();
    render(<WhatsAppInbox />);
    await waitFor(() => expect(screen.getByLabelText('WhatsApp message')).toBeInTheDocument());
    const input = screen.getByLabelText('WhatsApp message');

    await user.type(input, 'First');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await user.clear(input);
    await user.type(input, 'Second');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await user.clear(input);
    await user.type(input, 'First');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(mocks.send.mock.calls[0][0].idempotency_key).not.toBe(
      mocks.send.mock.calls[1][0].idempotency_key
    );
    expect(mocks.send.mock.calls[0][0].idempotency_key).toBe(
      mocks.send.mock.calls[2][0].idempotency_key
    );
  });

  it('does not clear a newer draft when an earlier send finishes', async () => {
    mocks.permissions.add(PERMISSIONS.WHATSAPP.READ_ALL);
    mocks.permissions.add(PERMISSIONS.WHATSAPP.SEND);
    mocks.params = new URLSearchParams('conversation=conversation-a');
    mocks.detail.mockReturnValue({ data: conversation, isLoading: false, isError: false });
    let resolveSend!: () => void;
    mocks.send.mockImplementationOnce(() => new Promise((resolve) => {
      resolveSend = () => resolve({});
    }));
    const user = userEvent.setup();
    render(<WhatsAppInbox />);
    const input = await screen.findByLabelText('WhatsApp message');

    await user.type(input, 'Earlier message');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await user.clear(input);
    await user.type(input, 'New draft');
    resolveSend();

    await waitFor(() => expect(input).toHaveValue('New draft'));
  });

  it('marks only the newest successfully displayed inbound message as read', async () => {
    mocks.permissions.add(PERMISSIONS.WHATSAPP.READ_ALL);
    mocks.params = new URLSearchParams('conversation=conversation-a');
    mocks.detail.mockReturnValue({ data: conversation, isLoading: false, isError: false });
    mocks.messages.mockReturnValue({
      data: [
        { id: 'inbound-1', direction: 'INBOUND', source: 'CUSTOMER', message_type: 'text', body: 'One', status: 'RECEIVED', error_code: null, error_message: null, media_available: false, created_at: new Date().toISOString(), provider_timestamp: null, sent_at: null, delivered_at: null, read_at: null },
        { id: 'inbound-2', direction: 'INBOUND', source: 'CUSTOMER', message_type: 'text', body: 'Two', status: 'RECEIVED', error_code: null, error_message: null, media_available: false, created_at: new Date().toISOString(), provider_timestamp: null, sent_at: null, delivered_at: null, read_at: null },
      ],
      isLoading: false,
      isError: false,
    });

    render(<WhatsAppInbox />);

    await waitFor(() => expect(mocks.action).toHaveBeenCalledWith({ type: 'read', message_id: 'inbound-2' }));
  });

  it('paginates beyond the first conversation page', async () => {
    mocks.permissions.add(PERMISSIONS.WHATSAPP.READ_ALL);
    mocks.list.mockReturnValue({
      data: Array.from({ length: 50 }, (_, index) => ({
        ...conversation,
        id: `conversation-${index}`,
        identity_id: `identity-${index}`,
        customer_phone: `+1415555${String(index).padStart(4, '0')}`,
      })),
      isLoading: false,
      isError: false,
    });
    const user = userEvent.setup();
    render(<WhatsAppInbox />);

    await user.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith('', 50, true));
  });

  it('can return from an empty message page at an exact page boundary', async () => {
    mocks.permissions.add(PERMISSIONS.WHATSAPP.READ_ALL);
    mocks.params = new URLSearchParams('conversation=conversation-a');
    mocks.detail.mockReturnValue({ data: conversation, isLoading: false, isError: false });
    const page = Array.from({ length: 100 }, (_, index) => ({
      id: `message-${index}`,
      direction: 'INBOUND',
      source: 'CUSTOMER',
      message_type: 'text',
      body: `Message ${index}`,
      status: 'RECEIVED',
      error_code: null,
      error_message: null,
      media_available: false,
      created_at: new Date().toISOString(),
      provider_timestamp: null,
      sent_at: null,
      delivered_at: null,
      read_at: null,
    }));
    mocks.messages.mockImplementation((_id: string, offset: number) => ({
      data: offset === 0 ? page : [],
      isLoading: false,
      isError: false,
    }));
    const user = userEvent.setup();
    render(<WhatsAppInbox />);

    await user.click(screen.getByRole('button', { name: 'Older' }));
    await waitFor(() => expect(screen.getByText('No messages yet.')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Newer' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Newer' }));

    await waitFor(() => expect(mocks.messages).toHaveBeenLastCalledWith('conversation-a', 0, true));
  });
});
