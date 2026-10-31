// src/queries.js
// Shared data hooks so Home, History and Garage hit the same React Query cache entries.
import { useQuery } from "@tanstack/react-query";
import { api, getAll } from "../api.js";

// Exported so mutations elsewhere (Garage, AddCar) can invalidate by the same key.
export const carsKey = ["history-cars"];
export const categoriesKey = ["history-categories"];
export const sessionsKey = ["history-sessions"];

export const useCars = () => useQuery({ queryKey: carsKey, queryFn: () => getAll("/garage/cars/") });

export const useCategories = () =>
  useQuery({ queryKey: categoriesKey, queryFn: () => getAll("/knowledge/categories/") });

export const useSessions = (carId = "", page = 1) =>
  useQuery({
    queryKey: [...sessionsKey, carId, page],
    queryFn: () => api(`/sessions/?${carId ? `car=${carId}&` : ""}page=${page}`),
    placeholderData: (previous) => previous,
  });

// Where a session row should link to. Single source of truth for Home + History.
export const sessionTarget = (s) =>
  s.status === "completed"
    ? s.has_outcome
      ? `/result/${s.id}`
      : `/outcome/${s.id}`
    : `/diagnose/${s.id}`;