// CRM Core Domain Types

export type UserRole =
  | 'Super Admin'
  | 'Organization Admin'
  | 'Sales Manager'
  | 'Sales Executive'
  | 'Marketing Executive'
  | 'Customer Support';

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  avatar?: string;
  organizationId: string;
  createdAt: string;
  permissions?: string[];
}

export interface Lead {
  id: string;
  title: string;
  company: string;
  contactName: string;
  email: string;
  phone: string;
  status: 'New' | 'Contacted' | 'Qualified' | 'Unqualified' | 'Converted';
  score?: number; // AI Lead Score
  assignedTo?: string;
  createdAt: string;
}

export interface Contact {
  id: string;
  name: string;
  email: string;
  phone: string;
  companyId?: string;
  position?: string;
  createdAt: string;
}

export interface Company {
  id: string;
  name: string;
  industry: string;
  website?: string;
  size?: string;
  createdAt: string;
}

export type DealStage = 'Prospecting' | 'Qualification' | 'Proposal' | 'Negotiation' | 'Closed Won' | 'Closed Lost';

export interface Deal {
  id: string;
  title: string;
  amount: number;
  stage: DealStage;
  contactId?: string;
  companyId?: string;
  expectedCloseDate: string;
  probability: number;
  assignedTo: string;
}

export interface Task {
  id: string;
  title: string;
  description?: string;
  dueDate: string;
  priority: 'Low' | 'Medium' | 'High' | 'Urgent';
  status: 'Pending' | 'In Progress' | 'Completed';
  assignedTo: string;
}

export interface Meeting {
  id: string;
  title: string;
  startTime: string;
  endTime: string;
  attendees: string[];
  meetingLink?: string;
  summary?: string; // AI Meeting Summary
}

export interface Call {
  id: string;
  contactId: string;
  type: 'Inbound' | 'Outbound';
  duration: number; // in seconds
  notes?: string;
  timestamp: string;
}

export interface Email {
  id: string;
  to: string[];
  from: string;
  subject: string;
  body: string;
  sentAt: string;
  isAiGenerated?: boolean;
}

export interface Note {
  id: string;
  entityType: 'Lead' | 'Contact' | 'Deal' | 'Company';
  entityId: string;
  content: string;
  createdBy: string;
  createdAt: string;
}

export interface Document {
  id: string;
  name: string;
  url: string;
  size: number;
  type: string;
  uploadedAt: string;
}

export interface Product {
  id: string;
  name: string;
  sku: string;
  price: number;
  category: string;
}

export interface Quote {
  id: string;
  quoteNumber: string;
  dealId?: string;
  items: { productId: string; quantity: number; unitPrice: number }[];
  totalAmount: number;
  status: 'Draft' | 'Sent' | 'Accepted' | 'Declined';
  validUntil: string;
}

export interface Invoice {
  id: string;
  invoiceNumber: string;
  quoteId?: string;
  amount: number;
  status: 'Draft' | 'Issued' | 'Paid' | 'Overdue';
  dueDate: string;
  issuedAt: string;
}

export interface Report {
  id: string;
  title: string;
  type: 'Sales Forecast' | 'Lead Conversion' | 'Revenue' | 'Activity';
  data: Record<string, unknown>;
  createdAt: string;
}

export interface Notification {
  id: string;
  userId: string;
  title: string;
  message: string;
  isRead: boolean;
  createdAt: string;
}

/** Common shape for related records returned by detail endpoints. */
export interface RelatedRecord {
  id: string;
  name?: string;
  title?: string;
  email?: string;
  content?: string;
  status?: string;
  type?: string;
  created_at?: string;
  updated_at?: string;
  body_text?: string;
  call_type?: string;
  duration_seconds?: number;
  total_amount?: number;
  amount_due?: number;
  number?: string;
  file_type?: string;
  file_url?: string;
  domain?: string;
  key_drivers?: string[];
  [key: string]: string | number | boolean | string[] | null | undefined;
}

export interface CompanyItemReference {
  id: string;
  name: string;
  domain?: string;
}

export interface CompanyHierarchy {
  parent?: CompanyItemReference | null;
  parent_company?: CompanyItemReference | null;
  subsidiaries: CompanyItemReference[];
}

export interface DealStageItem {
  id: string;
  name: string;
  probability: number;
}

export interface DealWinLossAnalytics {
  win_rate: number;
  won_count: number;
  lost_count: number;
  top_loss_reasons: Array<{ reason: string; count: number }>;
}

export interface DealProductItem extends RelatedRecord {
  product_id: string;
  quantity: number;
  unit_price: number;
}

export interface DealCommissionResponse {
  commission: number;
  rate?: number;
  commission_rate_pct?: number;
  estimated_commission?: number;
}

export interface DealPredictionResponse {
  deal_id: string;
  predicted_probability: number;
  key_drivers: string[];
  ai_recommendation: string;
  risk_factors: string[];
  run_id?: string | null;
}

export interface ActionResponse {
  message: string;
  status?: string;
}
