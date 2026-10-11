"use client";

import { createContext, useContext } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Review } from "@/lib/api";

const Ctx = createContext<{ review: Review; refresh: () => void } | null>(null);

export function useReviewQuery(id: string) {
  return useQuery<Review>({ queryKey: ["review", id], queryFn: () => api.get(`/reviews/${id}`) });
}

export function ReviewProvider({ review, children }: { review: Review; children: React.ReactNode }) {
  const qc = useQueryClient();
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["review", review.id] });
    qc.invalidateQueries({ queryKey: ["records", review.id] });
  };
  return <Ctx.Provider value={{ review, refresh }}>{children}</Ctx.Provider>;
}

export function useReview() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useReview outside ReviewProvider");
  return v;
}

export const canEdit = (role: string) => ["owner", "admin"].includes(role);
export const canReview = (role: string) => ["owner", "admin", "reviewer"].includes(role);
