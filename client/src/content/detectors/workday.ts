import type { JobInfo } from "../../lib/types";

const toTitleCase = (s: string): string =>
  s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const isWorkday = (): boolean =>
  location.hostname.endsWith(".myworkdayjobs.com");

export const extractWorkday = (): Partial<JobInfo> => {
  const company = location.hostname.split(".")[0];

  const titleEl =
    document.querySelector<HTMLElement>('[data-automation-id="jobPostingHeader"]') ??
    document.querySelector<HTMLElement>("h1");

  const locationEl = document.querySelector<HTMLElement>(
    '[data-automation-id="locations"]'
  );

  const descEl =
    document.querySelector<HTMLElement>('[data-automation-id="jobPostingDescription"]') ??
    document.querySelector<HTMLElement>('[data-automation-id="richTextEditor"]');

  const locationText = locationEl?.innerText?.trim() ?? "";

  return {
    platform: "workday",
    company: toTitleCase(company),
    title: titleEl?.innerText?.trim() ?? "",
    location: locationText,
    isRemote: /remote/i.test(locationText),
    description: descEl?.innerText?.trim() ?? "",
  };
};
