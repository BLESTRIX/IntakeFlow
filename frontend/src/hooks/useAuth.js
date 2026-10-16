import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

export function useAuth() {
  return useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        return await api('/auth/me');
      } catch (error) {
        if (error.status === 401) return null;
        throw error;
      }
    },
    retry: false,
    staleTime: 60_000,
  });
}
