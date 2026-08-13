import { z } from 'zod';

export const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
});

export const registerSchema = z.object({
  name: z.string().min(2, 'Name is required'),
  email: z.string().email('Invalid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
  organizationName: z.string().min(2, 'Organization name is required'),
});

export const leadSchema = z.object({
  title: z.string().min(2, 'Title is required'),
  company: z.string().min(2, 'Company name is required'),
  contactName: z.string().min(2, 'Contact name is required'),
  email: z.string().email('Invalid email address'),
  phone: z.string().optional(),
  status: z.enum(['New', 'Contacted', 'Qualified', 'Unqualified', 'Converted']),
});

export const dealSchema = z.object({
  title: z.string().min(2, 'Deal title is required'),
  amount: z.number().positive('Amount must be positive'),
  stage: z.enum(['Prospecting', 'Qualification', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost']),
  expectedCloseDate: z.string(),
  probability: z.number().min(0).max(100),
  assignedTo: z.string(),
});

export const taskSchema = z.object({
  title: z.string().min(2, 'Task title is required'),
  description: z.string().optional(),
  dueDate: z.string(),
  priority: z.enum(['Low', 'Medium', 'High', 'Urgent']),
  assignedTo: z.string(),
});
