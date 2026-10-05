/**
 * Data hooks (TanStack Query): caching, loading and error states in one place.
 * A screen says what it needs; the hook knows where it lives.
 */
import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "./client";
import type {
  Approval, ChatAnswer, ClientSummary, EmailDraft, Overview, Retirement, SkillResult, StressTest,
} from "./types";

export const useClients = () =>
  useQuery({ queryKey: ["clients"], queryFn: ({ signal }) => api.get<ClientSummary[]>("/v1/clients", signal) });

export const useOverview = (clientId: string) =>
  useQuery({
    queryKey: ["overview", clientId],
    queryFn: ({ signal }) => api.get<Overview>(`/v1/clients/${encodeURIComponent(clientId)}/overview`, signal),
    staleTime: 60_000,
  });

const skill = <T>(agent: string, name: string, input: Record<string, unknown>) =>
  api.post<SkillResult<T>>(`/v1/skills/${agent}/${name}`, { input });

export const useRetirement = (clientId: string, retireAges: number[], spending: number | null) =>
  useQuery({
    queryKey: ["retirement", clientId, retireAges, spending],
    queryFn: () =>
      skill<Retirement>("actuary", "project_retirement", {
        client_id: clientId,
        ...(retireAges.length ? { retire_ages: retireAges } : {}),
        ...(spending ? { annual_spending: spending } : {}),
      }),
    placeholderData: (previous) => previous, // keep the old numbers on screen while the new ones compute
  });

export const useStressTest = (clientId: string, enabled: boolean) =>
  useQuery({
    queryKey: ["stress", clientId],
    queryFn: () => skill<StressTest>("actuary", "stress_test", { client_id: clientId }),
    enabled,
  });

export const useDraftEmail = () =>
  useMutation({
    mutationFn: (v: { clientId: string; purpose: string; points: string[] }) =>
      skill<EmailDraft>("herald", "draft_email", { client_id: v.clientId, purpose: v.purpose, points: v.points }),
  });

export const useApproveDraft = () =>
  useMutation({
    mutationFn: (v: { clientId: string; subject: string; body: string }) =>
      api.post<Approval>("/v1/drafts/approve", { client_id: v.clientId, subject: v.subject, body: v.body }),
  });

export const useAsk = () =>
  useMutation({
    mutationFn: (v: { message: string; clientId: string | null }) =>
      api.post<ChatAnswer>("/v1/chat", { message: v.message, ...(v.clientId ? { client_id: v.clientId } : {}) }),
  });
