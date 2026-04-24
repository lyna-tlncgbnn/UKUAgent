import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  changePassword,
  getAuthSession,
  getUserProfile,
  signInWithPassword,
  signOut,
  updateAccount,
  updateUserProfile,
} from "./api";

export function useAuthSession() {
  return useQuery({
    queryKey: ["auth", "session"],
    queryFn: getAuthSession,
    refetchOnWindowFocus: false,
  });
}

export function useSignIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: signInWithPassword,
    onSuccess(session) {
      void queryClient.setQueryData(["auth", "session"], session);
    },
  });
}

export function useSignOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: signOut,
    onSuccess() {
      void queryClient.setQueryData(["auth", "session"], null);
      void queryClient.invalidateQueries({ queryKey: ["threads", "search"] });
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: changePassword,
  });
}

export function useUpdateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateAccount,
    onSuccess(session) {
      void queryClient.setQueryData(["auth", "session"], session);
    },
  });
}

export function useUserProfile() {
  return useQuery({
    queryKey: ["auth", "user-profile"],
    queryFn: getUserProfile,
    refetchOnWindowFocus: false,
  });
}

export function useUpdateUserProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateUserProfile,
    onSuccess(profile) {
      void queryClient.setQueryData(["auth", "user-profile"], profile);
    },
  });
}
