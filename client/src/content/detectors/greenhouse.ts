import type { JobInfo } from "../../lib/types";

const toTitleCase = (s: string): string =>
  s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const isGreenhouse = (): boolean =>
  location.hostname === "boards.greenhouse.io" ||
  location.hostname === "job-boards.greenhouse.io";

export const extractGreenhouse = (): Partial<JobInfo> => {
  const parts = location.pathname.split("/").filter(Boolean);
  const company = parts[0] ?? "";

  const titleEl =
    document.querySelector<HTMLElement>("h1.app-title") ??
    document.querySelector<HTMLElement>("h1");

  const locationEl = document.querySelector<HTMLElement>(".location");
  const locationText = locationEl?.innerText?.trim() ?? "";

  return {
    platform: "greenhouse",
    company: toTitleCase(company),
    title: titleEl?.innerText?.trim() ?? "",
    location: locationText,
    isRemote: /remote/i.test(locationText),
  };
};
