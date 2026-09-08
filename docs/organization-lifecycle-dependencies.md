# Organization dependency inventory

Generated from imported SQLAlchemy metadata after lifecycle changes. Production FK audit was separately read-only; this file is not proof of a deployed migration.

| Table | Ownership | Foreign keys (delete rule) |
| --- | --- | --- |
| activity_logs | organization_id | organization_id → organizations.id (CASCADE); user_id → users.id (CASCADE) |
| ai_actions | organization_id | organization_id → organizations.id (CASCADE); run_id → ai_runs.id (CASCADE); user_id → users.id (CASCADE) |
| ai_conversations | organization_id | organization_id → organizations.id (CASCADE); user_id → users.id (CASCADE) |
| ai_generated_contents | organization_id | organization_id → organizations.id (CASCADE); user_id → users.id (CASCADE) |
| ai_lead_scores | lead_id → leads | lead_id → leads.id (CASCADE) |
| ai_meeting_summaries | meeting_id → meetings | meeting_id → meetings.id (CASCADE) |
| ai_organization_configs | organization_id | organization_id → organizations.id (CASCADE) |
| ai_prompts | conversation_id → ai_conversations | conversation_id → ai_conversations.id (CASCADE); run_id → ai_runs.id (SET NULL) |
| ai_runs | organization_id | organization_id → organizations.id (CASCADE); user_id → users.id (CASCADE) |
| ai_transcripts | organization_id | organization_id → organizations.id (CASCADE); run_id → ai_runs.id (CASCADE); user_id → users.id (CASCADE) |
| api_keys | organization_id | created_by → users.id (SET NULL); organization_id → organizations.id (CASCADE) |
| audit_logs | organization_id | organization_id → organizations.id (CASCADE); user_id → users.id (SET NULL) |
| calendar_events | user_id → users | user_id → users.id (CASCADE) |
| call_logs | organization_id | company_id → companies.id (SET NULL); contact_id → contacts.id (SET NULL); deal_id → deals.id (SET NULL); lead_id → leads.id (SET NULL); organization_id → organizations.id (CASCADE) |
| cities | Global / unscoped; retained | state_id → states.id (CASCADE) |
| companies | organization_id | organization_id → organizations.id (CASCADE); parent_company_id → companies.id (SET NULL) |
| company_contacts | company_id → companies | company_id → companies.id (CASCADE); contact_id → contacts.id (CASCADE) |
| contact_addresses | contact_id → contacts | contact_id → contacts.id (CASCADE) |
| contact_tags | contact_id → contacts | contact_id → contacts.id (CASCADE) |
| contacts | organization_id | organization_id → organizations.id (CASCADE) |
| countries | Global / unscoped; retained | — |
| currencies | Global / unscoped; retained | — |
| custom_fields | organization_id | organization_id → organizations.id (CASCADE) |
| custom_reports | organization_id | organization_id → organizations.id (CASCADE) |
| deal_activities | deal_id → deals | deal_id → deals.id (CASCADE); performed_by → users.id (SET NULL) |
| deal_products | deal_id → deals | deal_id → deals.id (CASCADE); product_id → products.id (RESTRICT) |
| deal_stage_history | organization_id | actor_id → users.id (SET NULL); deal_id → deals.id (CASCADE); organization_id → organizations.id (CASCADE) |
| deal_stages | organization_id | organization_id → organizations.id (CASCADE) |
| deals | organization_id | assigned_to → users.id (CASCADE); company_id → companies.id (SET NULL); contact_id → contacts.id (SET NULL); organization_id → organizations.id (CASCADE); project_id → projects.id (SET NULL) |
| document_versions | document_id → documents | document_id → documents.id (CASCADE) |
| documents | organization_id | company_id → companies.id (SET NULL); contact_id → contacts.id (SET NULL); deal_id → deals.id (SET NULL); invoice_id → invoices.id (SET NULL); lead_id → leads.id (SET NULL); organization_id → organizations.id (CASCADE); payment_id → payments.id (SET NULL); quote_id → quotes.id (SET NULL); uploaded_by → users.id (CASCADE) |
| email_logs | email_id → emails | email_id → emails.id (CASCADE) |
| email_templates | organization_id | organization_id → organizations.id (CASCADE) |
| email_verifications | user_id → users | user_id → users.id (CASCADE) |
| emails | organization_id | company_id → companies.id (SET NULL); contact_id → contacts.id (SET NULL); deal_id → deals.id (SET NULL); lead_id → leads.id (SET NULL); organization_id → organizations.id (CASCADE) |
| file_uploads | Global / unscoped; retained | — |
| integration_deliveries | organization_id | integration_id → integrations.id (CASCADE); organization_id → organizations.id (CASCADE) |
| integrations | organization_id | organization_id → organizations.id (CASCADE) |
| invoice_items | invoice_id → invoices | invoice_id → invoices.id (CASCADE); product_id → products.id (SET NULL) |
| invoices | organization_id | company_id → companies.id (SET NULL); contact_id → contacts.id (SET NULL); deal_id → deals.id (SET NULL); finalized_by → users.id (SET NULL); organization_id → organizations.id (CASCADE); quote_id → quotes.id (SET NULL); review_submitted_by → users.id (SET NULL) |
| languages | Global / unscoped; retained | — |
| lead_activities | lead_id → leads | lead_id → leads.id (CASCADE); performed_by → users.id (SET NULL) |
| lead_attachments | lead_id → leads | lead_id → leads.id (CASCADE) |
| lead_notes | lead_id → leads | created_by → users.id (CASCADE); lead_id → leads.id (CASCADE) |
| lead_scores | lead_id → leads | lead_id → leads.id (CASCADE) |
| lead_sources | organization_id | organization_id → organizations.id (CASCADE) |
| lead_statuses | organization_id | organization_id → organizations.id (CASCADE) |
| lead_tags | lead_id → leads | lead_id → leads.id (CASCADE) |
| leads | organization_id | assigned_to → users.id (SET NULL); converted_by → users.id (SET NULL); converted_company_id → companies.id (RESTRICT); converted_contact_id → contacts.id (RESTRICT); converted_deal_id → deals.id (RESTRICT); disqualified_by → users.id (SET NULL); organization_id → organizations.id (CASCADE); qualified_by → users.id (SET NULL) |
| magic_link_tokens | user_id → users | user_id → users.id (CASCADE) |
| meeting_attendees | meeting_id → meetings | meeting_id → meetings.id (CASCADE) |
| meetings | organization_id | company_id → companies.id (SET NULL); contact_id → contacts.id (SET NULL); deal_id → deals.id (SET NULL); lead_id → leads.id (SET NULL); organization_id → organizations.id (CASCADE) |
| notes | organization_id | company_id → companies.id (SET NULL); contact_id → contacts.id (SET NULL); created_by → users.id (CASCADE); deal_id → deals.id (SET NULL); lead_id → leads.id (SET NULL); organization_id → organizations.id (CASCADE) |
| notifications | organization_id | organization_id → organizations.id (CASCADE); user_id → users.id (CASCADE) |
| organization_deletions | Retained lifecycle record | actor_id → users.id (RESTRICT) |
| organization_file_cleanups | Retained lifecycle record | operation_id → organization_deletions.id (CASCADE) |
| organization_invitations | organization_id | organization_id → organizations.id (CASCADE) |
| organization_settings | organization_id | organization_id → organizations.id (CASCADE) |
| organization_subscriptions | organization_id | organization_id → organizations.id (CASCADE); plan_id → subscription_plans.id (SET NULL) |
| organizations | Tenant parent | — |
| otp_verifications | user_id → users | user_id → users.id (CASCADE) |
| password_resets | user_id → users | user_id → users.id (CASCADE) |
| payments | organization_id | invoice_id → invoices.id (RESTRICT); organization_id → organizations.id (RESTRICT); recorded_by → users.id (SET NULL) |
| permissions | Global / unscoped; retained | — |
| processed_webhook_events | Global / unscoped; retained | — |
| product_categories | organization_id | organization_id → organizations.id (CASCADE) |
| products | organization_id | category_id → product_categories.id (SET NULL); organization_id → organizations.id (CASCADE) |
| projects | organization_id | organization_id → organizations.id (CASCADE); owner_id → users.id (SET NULL) |
| quote_delivery_attempts | organization_id | organization_id → organizations.id (CASCADE); quote_id → quotes.id (CASCADE) |
| quote_items | quote_id → quotes | product_id → products.id (SET NULL); quote_id → quotes.id (CASCADE) |
| quotes | organization_id | approved_by → users.id (SET NULL); automatic_deal_id → deals.id (RESTRICT); company_id → companies.id (RESTRICT); contact_id → contacts.id (RESTRICT); deal_id → deals.id (SET NULL); organization_id → organizations.id (CASCADE); review_submitted_by → users.id (SET NULL) |
| refresh_tokens | user_id → users | user_id → users.id (CASCADE) |
| report_exports | organization_id | organization_id → organizations.id (CASCADE); requested_by → users.id (CASCADE) |
| role_permissions | role_id → roles | permission_id → permissions.id (CASCADE); role_id → roles.id (CASCADE) |
| roles | organization_id | organization_id → organizations.id (CASCADE) |
| scheduled_reports | organization_id | organization_id → organizations.id (CASCADE) |
| settings | Global / unscoped; retained | — |
| sla_policies | organization_id | organization_id → organizations.id (CASCADE) |
| states | Global / unscoped; retained | country_id → countries.id (CASCADE) |
| subscription_plans | Global / unscoped; retained | — |
| task_attachments | task_id → tasks | task_id → tasks.id (CASCADE) |
| task_comments | task_id → tasks | task_id → tasks.id (CASCADE); user_id → users.id (CASCADE) |
| tasks | organization_id | assigned_to → users.id (CASCADE); company_id → companies.id (SET NULL); contact_id → contacts.id (SET NULL); deal_id → deals.id (SET NULL); lead_id → leads.id (SET NULL); organization_id → organizations.id (CASCADE); project_id → projects.id (SET NULL) |
| timezones | Global / unscoped; retained | — |
| user_invitations | organization_id | organization_id → organizations.id (CASCADE) |
| user_profiles | user_id → users | user_id → users.id (CASCADE) |
| user_quotas | organization_id | organization_id → organizations.id (CASCADE); user_id → users.id (CASCADE) |
| user_roles | user_id → users | role_id → roles.id (CASCADE); user_id → users.id (CASCADE) |
| user_sessions | user_id → users | user_id → users.id (CASCADE) |
| users | organization_id | organization_id → organizations.id (CASCADE) |
| webhooks | organization_id | organization_id → organizations.id (CASCADE) |
