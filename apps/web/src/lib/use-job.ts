"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, type Job } from "@/lib/api";

export const isLive = (job?: Job | null) => job?.status === "queued" || job?.status === "running";

/** Follows the review's long operations (duplicate detection, AI screening, AI extraction).
 *  The hosted service runs them in a worker: starting one answers at once with a queued job,
 *  which is then asked for every 1.5 seconds until it ends; `onEnd` is called once, whether it
 *  is done or failed. A job of one of `kinds` already under way when the page opens (after a
 *  reload, or started by a teammate) is followed too. Where jobs run inline (development),
 *  the job comes back finished and `onEnd` is called at once. */
export function useJob(reviewId: string, kinds: string[], onEnd: (job: Job) => void) {
  const qc = useQueryClient();
  const [started, setStarted] = useState<string | null>(null);
  const [ended, setEnded] = useState<string[]>([]);

  // Only a list fetched since the page opened counts: a cached one may still show as running
  // a job that has ended since, and was reported then.
  const recent = useQuery<Job[]>({
    queryKey: ["jobs", reviewId],
    queryFn: () => api.get(`/reviews/${reviewId}/jobs`),
    staleTime: 0,
    refetchOnMount: "always",
  });
  const underWay = recent.isFetchedAfterMount
    ? recent.data?.find((j) => kinds.includes(j.kind) && isLive(j) && !ended.includes(j.id))?.id
    : undefined;
  const id = started ?? underWay ?? null;
  const active = !!id && !ended.includes(id);

  const stop = (jobId: string) => {
    setEnded((e) => (e.includes(jobId) ? e : [...e, jobId]));
    setStarted((s) => (s === jobId ? null : s));
  };
  const finish = (job: Job) => {
    stop(job.id);
    qc.invalidateQueries({ queryKey: ["jobs", reviewId] });
    onEnd(job);
  };

  const followed = useQuery<Job>({
    queryKey: ["job", id],
    queryFn: async () => {
      try {
        const job = await api.get<Job>(`/jobs/${id}`);
        if (!isLive(job)) finish(job);
        return job;
      } catch (e) {
        if (e instanceof ApiError && (e.status === 403 || e.status === 404)) stop(id as string);   // gone, or not ours
        throw e;
      }
    },
    enabled: active,
    refetchInterval: (q) => (isLive(q.state.data) ? 1500 : false),
  });

  /** Follows a job just started; one that already ran (inline) ends at once. */
  const follow = (job: Job) => {
    if (!isLive(job)) return finish(job);
    qc.setQueryData(["job", job.id], job);
    setStarted(job.id);
  };

  // Until the first answer, a job found under way is shown as the list has it.
  const job = followed.data?.id === id ? followed.data : recent.data?.find((j) => j.id === id);
  // The review's latest jobs, newest first (fetched again whenever a followed job ends).
  return { follow, running: active, job: active ? job : undefined, jobs: recent.data ?? [] };
}
