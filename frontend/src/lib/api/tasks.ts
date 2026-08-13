import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface TaskItem {
  id: string;
  title: string;
  description?: string;
  priority?: string; // 'Low' | 'Medium' | 'High'
  due_date?: string;
  status?: string; // 'Pending' | 'In Progress' | 'Completed'
  assigned_to?: string;
  created_at?: string;
}

export interface TaskCreatePayload {
  title: string;
  description?: string;
  priority?: string;
  due_date?: string;
  status?: string;
  assigned_to?: string;
}

export interface TaskUpdatePayload {
  title?: string;
  description?: string;
  priority?: string;
  due_date?: string;
  status?: string;
  assigned_to?: string;
}

export interface FetchTasksParams {
  page?: number;
  limit?: number;
  search?: string;
  status?: string;
  priority?: string;
}

export interface SubtaskItem {
  id: string;
  task_id?: string;
  title: string;
  completed?: boolean;
  created_at?: string;
}

// ---------------------------------------------------------------------------
// Raw API Functions
// ---------------------------------------------------------------------------

export async function fetchTasksApi(params: FetchTasksParams = {}): Promise<TaskItem[]> {
  const query = new URLSearchParams();
  const page = params.page ?? 1;
  const limit = params.limit ?? 20;
  query.append('page', String(page));
  query.append('limit', String(limit));
  if (params.search) query.append('search', params.search);
  if (params.status) query.append('status', params.status);
  if (params.priority) query.append('priority', params.priority);

  const queryString = query.toString();
  return apiClient.get<TaskItem[]>(`/tasks${queryString ? `?${queryString}` : ''}`);
}

export async function getTaskByIdApi(id: string): Promise<TaskItem> {
  return apiClient.get<TaskItem>(`/tasks/${id}`);
}

export async function createTaskApi(payload: TaskCreatePayload): Promise<TaskItem> {
  return apiClient.post<TaskItem>('/tasks', payload);
}

export async function updateTaskApi(id: string, payload: TaskUpdatePayload): Promise<TaskItem> {
  return apiClient.put<TaskItem>(`/tasks/${id}`, payload);
}

export async function deleteTaskApi(id: string): Promise<{ message: string; status: string }> {
  return apiClient.delete<{ message: string; status: string }>(`/tasks/${id}`);
}

export async function completeTaskApi(id: string): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/tasks/${id}/complete`);
}

export async function reopenTaskApi(id: string): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/tasks/${id}/reopen`);
}

export async function fetchOverdueTasksApi(): Promise<TaskItem[]> {
  return apiClient.get<TaskItem[]>('/tasks/overdue');
}

export async function fetchTodayTasksApi(): Promise<TaskItem[]> {
  return apiClient.get<TaskItem[]>('/tasks/today');
}

export async function fetchBoardTasksApi(): Promise<Record<string, Array<{ id: string; title: string; priority?: string; due_date?: string; assigned_to?: string }>>> {
  return apiClient.get<Record<string, Array<{ id: string; title: string; priority?: string; due_date?: string; assigned_to?: string }>>>('/tasks/board-view');
}

export async function exportTasksCsvApi(): Promise<{ download_url: string }> {
  return apiClient.get<{ download_url: string }>('/tasks/export/csv');
}

export async function importTasksCsvApi(file: File): Promise<{ message: string; status: string }> {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient.post<{ message: string; status: string }>('/tasks/import/csv', formData);
}

export async function bulkDeleteTasksApi(ids: string[]): Promise<{ affected_count: number; message: string }> {
  return apiClient.post<{ affected_count: number; message: string }>('/tasks/bulk-delete', { ids });
}

export async function bulkCompleteTasksApi(ids: string[]): Promise<{ affected_count: number; message: string }> {
  return apiClient.post<{ affected_count: number; message: string }>('/tasks/bulk-complete', { ids });
}

export async function fetchSubtasksApi(taskId: string): Promise<SubtaskItem[]> {
  return apiClient.get<SubtaskItem[]>(`/tasks/${taskId}/subtasks`);
}

export async function addSubtaskApi(taskId: string, title: string): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/tasks/${taskId}/subtasks?title=${encodeURIComponent(title)}`);
}

export async function assignTaskApi(taskId: string, userId: string): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/tasks/${taskId}/assign?user_id=${encodeURIComponent(userId)}`);
}

export async function setTaskReminderApi(taskId: string, reminderTime: string): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/tasks/${taskId}/reminder?reminder_time=${encodeURIComponent(reminderTime)}`);
}

// ---------------------------------------------------------------------------
// TanStack Query Hooks
// ---------------------------------------------------------------------------

export function useTasksQuery(params: FetchTasksParams = {}) {
  return useQuery({
    queryKey: ['tasks', params],
    queryFn: () => fetchTasksApi(params),
    placeholderData: (previousData) => previousData,
  });
}

export function useTaskQuery(id: string) {
  return useQuery({
    queryKey: ['task', id],
    queryFn: () => getTaskByIdApi(id),
    enabled: !!id,
  });
}

export function useOverdueTasksQuery() {
  return useQuery({
    queryKey: ['tasks', 'overdue'],
    queryFn: () => fetchOverdueTasksApi(),
  });
}

export function useTodayTasksQuery() {
  return useQuery({
    queryKey: ['tasks', 'today'],
    queryFn: () => fetchTodayTasksApi(),
  });
}

export function useBoardTasksQuery() {
  return useQuery({
    queryKey: ['tasks', 'board-view'],
    queryFn: () => fetchBoardTasksApi(),
  });
}

export function useSubtasksQuery(taskId: string) {
  return useQuery({
    queryKey: ['tasks', taskId, 'subtasks'],
    queryFn: () => fetchSubtasksApi(taskId),
    enabled: !!taskId,
  });
}

export function useCreateTaskMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: TaskCreatePayload) => createTaskApi(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useUpdateTaskMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TaskUpdatePayload }) => updateTaskApi(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useDeleteTaskMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteTaskApi(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useCompleteTaskMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => completeTaskApi(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useReopenTaskMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => reopenTaskApi(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useBulkDeleteTasksMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ids: string[]) => bulkDeleteTasksApi(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useBulkCompleteTasksMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ids: string[]) => bulkCompleteTasksApi(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useAddSubtaskMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ taskId, title }: { taskId: string; title: string }) => addSubtaskApi(taskId, title),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['tasks', variables.taskId, 'subtasks'] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useAssignTaskMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ taskId, userId }: { taskId: string; userId: string }) => assignTaskApi(taskId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useSetTaskReminderMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ taskId, reminderTime }: { taskId: string; reminderTime: string }) => setTaskReminderApi(taskId, reminderTime),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}
