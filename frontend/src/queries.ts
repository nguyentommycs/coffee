import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ApiError, addBeans, getBeans, getProfile, getRecommendationRuns, getRecommendations } from './api'

export function useBeans(userId: string) {
  return useQuery({
    queryKey: ['beans', userId],
    queryFn: () => getBeans(userId),
  })
}

export function useProfile(userId: string) {
  return useQuery({
    queryKey: ['profile', userId],
    queryFn: () => getProfile(userId),
    retry: (count, error) => {
      if (error instanceof ApiError && error.status === 404) return false
      return count < 3
    },
  })
}

export function usePastRuns(userId: string) {
  return useQuery({
    queryKey: ['pastRuns', userId],
    queryFn: () => getRecommendationRuns(userId),
  })
}

export function useAddBean(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: string) => addBeans(userId, [input]),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['beans', userId] })
    },
  })
}

export function useRunRecommendations(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (n?: number) => getRecommendations(userId, n),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile', userId] })
      queryClient.invalidateQueries({ queryKey: ['pastRuns', userId] })
    },
  })
}
