import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { BeanEditableFields } from './api'
import type { FeedbackVerdict } from './types'
import {
  ApiError,
  addBeans,
  deleteFeedback,
  fetchTrace,
  fetchTraces,
  getBeans,
  getFeedback,
  getProfile,
  getProgress,
  getRecommendationRuns,
  getRecommendations,
  postFeedback,
  updateBean,
} from './api'

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

export function useTraces(userId: string) {
  return useQuery({
    queryKey: ['traces', userId],
    queryFn: () => fetchTraces(userId),
  })
}

export function useTrace(userId: string, runId: string | null) {
  return useQuery({
    queryKey: ['trace', userId, runId],
    queryFn: () => fetchTrace(userId, runId as string),
    enabled: runId !== null,
    staleTime: Infinity, // traces are immutable once written
  })
}

export function useAddBean(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ input, score }: { input: string; score: number }) =>
      addBeans(userId, [input], score),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['beans', userId] })
    },
  })
}

export function useUpdateBean(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ beanId, fields }: { beanId: string; fields: BeanEditableFields }) =>
      updateBean(userId, beanId, fields),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['beans', userId] })
    },
  })
}

export function useRunRecommendations(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ n, progressId }: { n?: number; progressId?: string }) =>
      getRecommendations(userId, n, progressId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile', userId] })
      queryClient.invalidateQueries({ queryKey: ['pastRuns', userId] })
    },
  })
}

/** Polls pipeline progress while a run is in flight. Pass null to stop polling. */
export function usePipelineProgress(progressId: string | null) {
  return useQuery({
    queryKey: ['pipelineProgress', progressId],
    queryFn: () => getProgress(progressId as string),
    enabled: progressId !== null,
    refetchInterval: 750,
    retry: false,
    gcTime: 0,
  })
}

export function useFeedback(userId: string) {
  return useQuery({
    queryKey: ['feedback', userId],
    queryFn: () => getFeedback(userId),
  })
}

export function useSetFeedback(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      roaster,
      name,
      product_url,
      verdict,
    }: {
      roaster: string
      name: string
      product_url: string
      verdict: FeedbackVerdict | null
    }) => {
      if (verdict === null) await deleteFeedback(userId, roaster, name)
      else await postFeedback(userId, { roaster, name, product_url, verdict })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feedback', userId] })
    },
  })
}
