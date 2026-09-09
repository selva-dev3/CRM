import { z } from 'zod';

const date = z.string().nullable();
export const whatsappIntegrationSchema = z.object({
  configured: z.boolean(), enabled: z.boolean(), phone_index_ready: z.boolean(), status: z.string(),
  business_account_id: z.string().nullable(), phone_number_id: z.string().nullable(),
  display_phone_number: z.string().nullable(), verified_name: z.string().nullable(),
  api_version: z.string().nullable(), default_phone_region: z.string().nullable(), last_webhook_at: date, last_successful_message_at: date,
  ai_user_id: z.string().nullable(), default_assignee_id: z.string().nullable(),
});
export const whatsappConversationSchema = z.object({
  id: z.string(), identity_id: z.string(), status: z.enum(['OPEN', 'HUMAN_HANDOFF', 'CLOSED']),
  ai_enabled: z.boolean(), assigned_user_id: z.string().nullable(),
  last_customer_message_at: date, last_message_at: date, customer_phone: z.string(),
  identity_state: z.enum(['UNKNOWN', 'AMBIGUOUS', 'MATCHED_CONTACT', 'MATCHED_LEAD']),
  consent: z.enum(['UNKNOWN', 'OPTED_IN', 'OPTED_OUT']),
  contact_id: z.string().nullable(), lead_id: z.string().nullable(), unread_count: z.number().int().nonnegative(),
});
export const whatsappMessageSchema = z.object({
  id: z.string(), direction: z.enum(['INBOUND', 'OUTBOUND']), source: z.string(), message_type: z.string(),
  body: z.string().nullable(), status: z.enum(['RECEIVED', 'PENDING', 'PROCESSING', 'ACCEPTED', 'SENT', 'DELIVERED', 'READ', 'FAILED', 'UNKNOWN']),
  error_code: z.string().nullable(), error_message: z.string().nullable(), media_available: z.boolean(), created_at: z.string(), provider_timestamp: date, sent_at: date, delivered_at: date, read_at: date,
});
export const whatsappTemplateSchema = z.object({ id: z.string(), name: z.string(), language: z.string(), category: z.string(), status: z.string(), body_parameter_count: z.number().int().nonnegative() });
export const whatsappAssigneeSchema = z.object({ id: z.string(), name: z.string() });
export const whatsappConfigFormSchema = z.object({
  business_account_id: z.string().regex(/^\d{1,100}$/, 'Enter the business account ID.'),
  phone_number_id: z.string().regex(/^\d{1,100}$/, 'Enter the phone number ID.'),
  access_token: z.string().min(20, 'Enter a valid access token.').max(4096),
  api_version: z.string().regex(/^v\d{2}\.0$/, 'Enter the supported Meta API version, such as vNN.0.'),
  default_phone_region: z.string().regex(/^([A-Z]{2})?$/, 'Use an ISO two-letter region or leave empty.'),
  ai_user_id: z.string().max(36), default_assignee_id: z.string().min(1, 'Select a default assignee.').max(36),
});
export const whatsappMessageFormSchema = z.object({ body: z.string().trim().min(1, 'Enter a message.').max(4096) });
export type WhatsAppConfigForm = z.infer<typeof whatsappConfigFormSchema>;
export type WhatsAppConversationDto = z.infer<typeof whatsappConversationSchema>;
export type WhatsAppMessageDto = z.infer<typeof whatsappMessageSchema>;
export type WhatsAppTemplateDto = z.infer<typeof whatsappTemplateSchema>;
