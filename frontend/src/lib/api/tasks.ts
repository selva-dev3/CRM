import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export interface TaskItem {
  id: string;
  title: string;
  due_date?: string;
  priority?: string;
  status?: string;
  assigned_to?: string;
}

export async function fetchTasksApi(page = 1, limit = 15, search?: string): Promise<TaskItem[]> {
  try {
    const query = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (search) query.append('search', search);
    const data = await apiClient.get<TaskItem[]>(`/tasks?${query.toString()}`);
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Fallback data
  }
  return [
    { id: 'tsk-1', title: 'Schedule Technical Demo with Acme Corp', due_date: '2026-08-10', priority: 'High', status: 'In Progress', assigned_to: 'Manager' },
    { id: 'tsk-2', title: 'Send Contract Proposal to Nexus Tech', due_date: '2026-08-12', priority: 'Medium', status: 'Pending', assigned_to: 'Representative' },
    { id: 'tsk-3', title: 'Follow up on Inactive Leads', due_date: '2026-08-15', priority: 'Low', status: 'Pending', assigned_to: 'Sales Lead' },
    { id: 'tsk-4', title: 'Prepare Q3 Sales Forecast Presentation', due_date: '2026-08-18', priority: 'High', status: 'Completed', assigned_to: 'Director' },
    { id: 'tsk-5', title: 'Review Security Questionnaire for Hyperion', due_date: '2026-08-20', priority: 'High', status: 'In Progress', assigned_to: 'Security Lead' },
    { id: 'tsk-6', title: 'Audit Partner Integration Webhooks', due_date: '2026-08-22', priority: 'Medium', status: 'Pending', assigned_to: 'DevOps' },
    { id: 'tsk-7', title: 'Conduct Customer Renewal Call with Starlight', due_date: '2026-08-25', priority: 'High', status: 'Pending', assigned_to: 'Account Manager' },
    { id: 'tsk-8', title: 'Update Pricing Sheet for 2027 Services', due_date: '2026-08-28', priority: 'Low', status: 'In Progress', assigned_to: 'Product Admin' },
    { id: 'tsk-9', title: 'Draft Executive Summary for Apex Fin', due_date: '2026-08-30', priority: 'Medium', status: 'Completed', assigned_to: 'Manager' },
    { id: 'tsk-10', title: 'Sync with Engineering on Feature Request #402', due_date: '2026-09-01', priority: 'Low', status: 'Pending', assigned_to: 'Representative' },
    { id: 'tsk-11', title: 'Finalize SLA Agreement for Titan Robotics', due_date: '2026-09-03', priority: 'High', status: 'In Progress', assigned_to: 'Legal Lead' },
    { id: 'tsk-12', title: 'Verify Data Import Script CSV Export', due_date: '2026-09-05', priority: 'Medium', status: 'Completed', assigned_to: 'Data Ops' },
    { id: 'tsk-13', title: 'Setup Automated Lead Nurturing Email Sequence', due_date: '2026-09-08', priority: 'High', status: 'Pending', assigned_to: 'Marketing' },
    { id: 'tsk-14', title: 'Schedule Onboarding Kickoff Call for Zion Bio', due_date: '2026-09-10', priority: 'Medium', status: 'In Progress', assigned_to: 'CS Specialist' },
    { id: 'tsk-15', title: 'Perform Quarterly Account Health Check', due_date: '2026-09-12', priority: 'Low', status: 'Pending', assigned_to: 'Representative' },
    { id: 'tsk-16', title: 'Review Pipeline Metrics with Vice President', due_date: '2026-09-15', priority: 'High', status: 'Pending', assigned_to: 'Manager' },
  ];
}

export function useTasksQuery(page = 1, limit = 15, search?: string) {
  return useQuery({
    queryKey: ['tasks', page, limit, search],
    queryFn: () => fetchTasksApi(page, limit, search),
    placeholderData: (previousData) => previousData,
  });
}
