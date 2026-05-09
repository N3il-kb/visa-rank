import type { JobInfo } from "../../lib/types";

const toTitleCase = (s: string): string =>
  s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const isLever = (): boolean => location.hostname === "jobs.lever.co";

export const extractLever = (): Partial<JobInfo> => {
  const parts = location.pathname.split("/").filter(Boolean);
  const company = parts[0] ?? "";

  const titleEl =
    document.querySelector<HTMLElement>("h2") ??
    document.querySelector<HTMLElement>("h1");

  const locationEl = document.querySelector<HTMLElement>(
    ".location, [class*='location']"
  );

  const locationText = locationEl?.innerText?.trim() ?? "";

  return {
    platform: "lever",
    company: toTitleCase(company),
    title: titleEl?.innerText?.trim() ?? "",
    location: locationText,
    isRemote: /remote/i.test(locationText),
  };
};
