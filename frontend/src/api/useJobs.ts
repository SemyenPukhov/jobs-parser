import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../lib/axios";

const fetchJobs = async () => {
  const { data } = await api.get("/jobs");
  return data;
};

export const useJobs = () => {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: fetchJobs,
  });
};

const fetchPendingJobs = async () => {
  const { data } = await api.get("/pending-jobs");
  return data;
};

export const usePendingJobs = () => {
  return useQuery({
    queryKey: ["pendingJobs"],
    queryFn: fetchPendingJobs,
  });
};

const fetchAcceptOrRejectJob = async (
  id: string,
  action: "accept" | "reject",
  comment: string
) => {
  const { data } = await api.post(`/jobs/${id}/${action}`, {
    comment,
  });
  return data;
};

export const useAcceptOrRejectJob = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
      comment,
    }: {
      id: string;
      action: "accept" | "reject";
      comment: string;
    }) => fetchAcceptOrRejectJob(id, action, comment),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["pendingJobs"] });
    },
  });
};
