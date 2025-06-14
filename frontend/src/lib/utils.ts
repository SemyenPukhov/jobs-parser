import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(isoDate: string) {
  const date = new Date(isoDate);

  const formatted = new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
  
  return formatted;
}


export function daysAgo(isoDate: string) {
  const parsedDate = new Date(isoDate).getTime();
  const now = new Date().getTime();

  const diffTime = now - parsedDate;

  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
  return diffDays;
}