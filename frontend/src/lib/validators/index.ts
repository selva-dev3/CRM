import { z } from 'zod';

export const loginSchema = z.object({
  email: z.string().trim().min(1, 'Work email is required').email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
  rememberMe: z.boolean(),
});

export const forgotPasswordSchema = z.object({
  email: z.string().trim().min(1, 'Work email is required').email('Enter a valid email address'),
});

export const resetPasswordSchema = z
  .object({
    newPassword: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .max(72, 'Password must be 72 characters or fewer'),
    confirmPassword: z.string().min(1, 'Confirm your new password'),
  })
  .refine((values) => values.newPassword === values.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

export const acceptUserInviteSchema = z
  .object({
    name: z.string().trim().min(2, 'Name must be at least 2 characters'),
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .max(72, 'Password must be 72 characters or fewer'),
    confirmPassword: z.string().min(1, 'Confirm your password'),
  })
  .refine((values) => values.password === values.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

export const registerSchema = z.object({
  name: z.string().min(2, 'Name is required'),
  email: z.string().email('Invalid email address'),
  password: z
    .string()
    .min(8, 'Password must be at least 8 characters')
    .max(72, 'Password must be 72 characters or fewer'),
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
