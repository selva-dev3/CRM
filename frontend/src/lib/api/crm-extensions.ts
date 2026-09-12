import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiClient } from '@/lib/api/client';

export interface PageResult<T> { items: T[]; total: number }
export interface Team { id: string; name: string; description: string | null; manager_id: string | null; is_active: boolean; member_count: number; created_at: string }
export interface TeamDetail extends Team { members: { user_id: string; name: string; email: string; is_primary: boolean }[] }
export interface Ticket { id: string; ticket_number: string; subject: string; description: string; status: string; priority: string; source: string; contact_id: string | null; company_id: string | null; assigned_to: string | null; team_id: string | null; sla_policy_id: string | null; first_response_due_at: string | null; resolution_due_at: string | null; resolved_at: string | null; created_at: string; updated_at: string }
export interface TicketComment { id:string; user_id:string; body:string; is_internal:boolean; created_at:string }
export interface Customer { entity_type: 'contact' | 'company'; entity_id: string; name: string; email: string | null; company_id: string | null; open_tickets: number }
export interface KnowledgeArticle { id: string; title: string; slug: string; summary: string | null; body: string; category: string | null; status: string; author_id: string | null; published_at: string | null; created_at: string; updated_at: string }
export interface SavedDashboard { id:string; owner_id:string|null; name:string; description:string|null; is_shared:boolean; widgets:{id:string;enabled?:boolean}[]; filters:Record<string,unknown>; created_at:string; updated_at:string }
export interface WorkflowDefinition { id:string; name:string; description:string|null; module:string; trigger:string; conditions:Record<string,unknown>[]; actions:Record<string,unknown>[]; is_active:boolean; created_by:string|null; created_at:string; updated_at:string }
export interface WorkflowRun { id:string; status:string; action_results:Record<string,unknown>[]; error:string|null; started_at:string; finished_at:string|null }

async function paged<T>(path: string): Promise<PageResult<T>> {
  const response = await apiClient.getWithMetadata<T[]>(path);
  return { items: response.data, total: Number(response.headers.get('X-Total-Count') ?? response.data.length) };
}

export const extensionKeys = {
  teams: (page: number, search: string) => ['teams', page, search] as const,
  team: (id: string) => ['teams', id] as const,
  tickets: (page: number, search: string, status: string) => ['tickets', page, search, status] as const,
  customers: (page: number, search: string) => ['customers', page, search] as const,
  articles: (page: number, search: string, status: string) => ['knowledge-base', page, search, status] as const,
};

export function useTeams(page: number, search: string) { return useQuery({ queryKey: extensionKeys.teams(page, search), queryFn: () => paged<Team>(`/teams?page=${page}&limit=20&search=${encodeURIComponent(search)}`) }); }
export function useTeam(id: string) { return useQuery({ queryKey: extensionKeys.team(id), queryFn: () => apiClient.get<TeamDetail>(`/teams/${id}`), enabled: Boolean(id) }); }
export function useCreateTeam() { const client = useQueryClient(); return useMutation({ mutationFn: (payload: {name: string; description?: string}) => apiClient.post<Team>('/teams', payload), onSuccess: () => client.invalidateQueries({queryKey:['teams']}) }); }
export function useUpdateTeam() { const client = useQueryClient(); return useMutation({ mutationFn: ({id, payload}:{id:string; payload:Partial<Team>}) => apiClient.patch<Team>(`/teams/${id}`, payload), onSuccess: () => client.invalidateQueries({queryKey:['teams']}) }); }
export function useDeleteTeam() { const client = useQueryClient(); return useMutation({ mutationFn: (id:string) => apiClient.delete<void>(`/teams/${id}`), onSuccess: () => client.invalidateQueries({queryKey:['teams']}) }); }
export function useAddTeamMember() { const client = useQueryClient(); return useMutation({ mutationFn: ({teamId,userId,isPrimary=false}:{teamId:string;userId:string;isPrimary?:boolean}) => apiClient.put<TeamDetail>(`/teams/${teamId}/members`, {user_id:userId,is_primary:isPrimary}), onSuccess: (_data, variables) => { client.invalidateQueries({queryKey:['teams']}); client.invalidateQueries({queryKey:extensionKeys.team(variables.teamId)}); } }); }
export function useRemoveTeamMember() { const client = useQueryClient(); return useMutation({ mutationFn: ({teamId,userId}:{teamId:string;userId:string}) => apiClient.delete<void>(`/teams/${teamId}/members/${userId}`), onSuccess: (_data, variables) => { client.invalidateQueries({queryKey:['teams']}); client.invalidateQueries({queryKey:extensionKeys.team(variables.teamId)}); } }); }

export function useTickets(page: number, search: string, status: string) { return useQuery({ queryKey: extensionKeys.tickets(page,search,status), queryFn: () => paged<Ticket>(`/tickets?page=${page}&limit=20&search=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}`) }); }
export function useTicket(id:string){return useQuery({queryKey:['tickets',id],queryFn:()=>apiClient.get<Ticket>(`/tickets/${id}`),enabled:Boolean(id)});}
export function useTicketComments(id:string){return useQuery({queryKey:['tickets',id,'comments'],queryFn:()=>apiClient.get<TicketComment[]>(`/tickets/${id}/comments`),enabled:Boolean(id)});}
export function useTicketArticles(id:string,enabled=true){return useQuery({queryKey:['tickets',id,'articles'],queryFn:()=>apiClient.get<KnowledgeArticle[]>(`/tickets/${id}/knowledge-articles`),enabled:Boolean(id)&&enabled});}
export function useCreateTicket() { const client=useQueryClient(); return useMutation({mutationFn:(payload:Record<string,unknown>)=>apiClient.post<Ticket>('/tickets',payload),onSuccess:()=>client.invalidateQueries({queryKey:['tickets']})}); }
export function useUpdateTicket() { const client=useQueryClient(); return useMutation({mutationFn:({id,payload}:{id:string;payload:Record<string,unknown>})=>apiClient.patch<Ticket>(`/tickets/${id}`,payload),onSuccess:()=>client.invalidateQueries({queryKey:['tickets']})}); }
export function useDeleteTicket() { const client=useQueryClient(); return useMutation({mutationFn:(id:string)=>apiClient.delete<void>(`/tickets/${id}`),onSuccess:()=>client.invalidateQueries({queryKey:['tickets']})}); }
export function useAddTicketComment(){const client=useQueryClient();return useMutation({mutationFn:({ticketId,body,isInternal}:{ticketId:string;body:string;isInternal:boolean})=>apiClient.post<TicketComment>(`/tickets/${ticketId}/comments`,{body,is_internal:isInternal}),onSuccess:(_data,variables)=>client.invalidateQueries({queryKey:['tickets',variables.ticketId,'comments']})});}
export function useLinkTicketArticle(){const client=useQueryClient();return useMutation({mutationFn:({ticketId,articleId}:{ticketId:string;articleId:string})=>apiClient.post<KnowledgeArticle>(`/tickets/${ticketId}/knowledge-articles`,{article_id:articleId}),onSuccess:(_data,variables)=>client.invalidateQueries({queryKey:['tickets',variables.ticketId,'articles']})});}
export function useUnlinkTicketArticle(){const client=useQueryClient();return useMutation({mutationFn:({ticketId,articleId}:{ticketId:string;articleId:string})=>apiClient.delete<void>(`/tickets/${ticketId}/knowledge-articles/${articleId}`),onSuccess:(_data,variables)=>client.invalidateQueries({queryKey:['tickets',variables.ticketId,'articles']})});}

export function useCustomers(page:number,search:string){return useQuery({queryKey:extensionKeys.customers(page,search),queryFn:()=>paged<Customer>(`/customers?page=${page}&limit=20&search=${encodeURIComponent(search)}`)});}
export function useArticles(page:number,search:string,status:string,enabled=true){return useQuery({queryKey:extensionKeys.articles(page,search,status),queryFn:()=>paged<KnowledgeArticle>(`/knowledge-base?page=${page}&limit=20&search=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}`),enabled});}
export function useCreateArticle(){const client=useQueryClient();return useMutation({mutationFn:(payload:Record<string,unknown>)=>apiClient.post<KnowledgeArticle>('/knowledge-base',payload),onSuccess:()=>client.invalidateQueries({queryKey:['knowledge-base']})});}
export function useUpdateArticle(){const client=useQueryClient();return useMutation({mutationFn:({id,payload}:{id:string;payload:Record<string,unknown>})=>apiClient.patch<KnowledgeArticle>(`/knowledge-base/${id}`,payload),onSuccess:()=>client.invalidateQueries({queryKey:['knowledge-base']})});}
export function usePublishArticle(){const client=useQueryClient();return useMutation({mutationFn:(id:string)=>apiClient.post<KnowledgeArticle>(`/knowledge-base/${id}/publish`),onSuccess:()=>client.invalidateQueries({queryKey:['knowledge-base']})});}
export function useDeleteArticle(){const client=useQueryClient();return useMutation({mutationFn:(id:string)=>apiClient.delete<void>(`/knowledge-base/${id}`),onSuccess:()=>client.invalidateQueries({queryKey:['knowledge-base']})});}
export function useSavedDashboards(){return useQuery({queryKey:['saved-dashboards'],queryFn:()=>paged<SavedDashboard>('/dashboards?page=1&limit=100')});}
export function useCreateSavedDashboard(){const client=useQueryClient();return useMutation({mutationFn:(payload:Record<string,unknown>)=>apiClient.post<SavedDashboard>('/dashboards',payload),onSuccess:()=>client.invalidateQueries({queryKey:['saved-dashboards']})});}
export function useUpdateSavedDashboard(){const client=useQueryClient();return useMutation({mutationFn:({id,payload}:{id:string;payload:Record<string,unknown>})=>apiClient.patch<SavedDashboard>(`/dashboards/${id}`,payload),onSuccess:()=>client.invalidateQueries({queryKey:['saved-dashboards']})});}
export function useDeleteSavedDashboard(){const client=useQueryClient();return useMutation({mutationFn:(id:string)=>apiClient.delete<void>(`/dashboards/${id}`),onSuccess:()=>client.invalidateQueries({queryKey:['saved-dashboards']})});}
export function useWorkflows(){return useQuery({queryKey:['workflows'],queryFn:()=>paged<WorkflowDefinition>('/workflows?page=1&limit=100')});}
export function useWorkflowRuns(id:string){return useQuery({queryKey:['workflows',id,'runs'],queryFn:()=>apiClient.get<WorkflowRun[]>(`/workflows/${id}/runs`),enabled:Boolean(id)});}
export function useCreateWorkflow(){const client=useQueryClient();return useMutation({mutationFn:(payload:Record<string,unknown>)=>apiClient.post<WorkflowDefinition>('/workflows',payload),onSuccess:()=>client.invalidateQueries({queryKey:['workflows']})});}
export function useUpdateWorkflow(){const client=useQueryClient();return useMutation({mutationFn:({id,payload}:{id:string;payload:Record<string,unknown>})=>apiClient.patch<WorkflowDefinition>(`/workflows/${id}`,payload),onSuccess:()=>client.invalidateQueries({queryKey:['workflows']})});}
export function useDeleteWorkflow(){const client=useQueryClient();return useMutation({mutationFn:(id:string)=>apiClient.delete<void>(`/workflows/${id}`),onSuccess:()=>client.invalidateQueries({queryKey:['workflows']})});}
