// Centralized axios instance with two interceptors.
//
// 1. Request interceptor: pulls JWT from localStorage and adds it as
//    `Authorization: Bearer <token>` header. So component code never
//    has to remember to include the token — every request is auth'd.
//
// 2. Response interceptor: if the server returns 401, clear the token
//    and redirect to /login. Centralized handling of expired sessions.

import axios, { AxiosError } from "axios";

export const TOKEN_KEY = "portfolio_builder_token";

export const apiClient = axios.create({
  baseURL: "/api",  // proxied by Vite to backend:8000
  timeout: 30_000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      // Use replace so back button doesn't return to a 401'd page.
      if (window.location.pathname !== "/login") {
        window.location.replace("/login");
      }
    }
    return Promise.reject(error);
  },
);
