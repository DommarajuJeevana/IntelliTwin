
"use client";

import { useCallback, useMemo } from "react";
import { api } from "./api";
import { useAuth } from "../context/AuthContext";

// Wraps the API methods with the current JWT.
// The returned client stays stable until the token changes.
export function useApi() {
  const { token } = useAuth();

  const get = useCallback(
    (path) => api.get(path, token),
    [token]
  );

  const post = useCallback(
    (path, body) => api.post(path, body, token),
    [token]
  );

  const put = useCallback(
    (path, body) => api.put(path, body, token),
    [token]
  );

  const del = useCallback(
    (path) => api.del(path, token),
    [token]
  );

  return useMemo(
    () => ({ get, post, put, del }),
    [get, post, put, del]
  );
}
