import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';

export const activeRequest = (request) =>
  request?.status === 'PROCESSING' || Boolean(request?.pending_command_id);
export function useRequest(id) {
  return useQuery({
    queryKey: ['request', id],
    queryFn: () => api(`/requests/${id}`),
    refetchInterval: (query) => (activeRequest(query.state.data) ? 1500 : false),
  });
}
export function useIntakeMutation(id, action, method = 'POST') {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ body, key }) => api(`/requests/${id}${action}`, { method, body, key }),
    onSuccess: () => {
      for (const prefix of [
        'request',
        'requests',
        'extractions',
        'draft',
        'dashboard',
        'work-orders',
        'notifications',
      ])
        client.invalidateQueries({ queryKey: [prefix] });
    },
  });
}
