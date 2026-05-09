import type { JobInfo } from "../../lib/types";

export const isLinkedIn = (): boolean =>
  location.hostname === "www.linkedin.com" &&
  location.pathname.startsWith("/jobs");

export const extractLinkedIn = (): Partial<JobInfo> => {
  const titleEl = document.querySelector<HTMLElement>(
    ".job-details-jobs-unified-top-card__job-title h1, .topcard__title"
  );

  const companyEl = document.querySelector<HTMLElement>(
    ".job-details-jobs-unified-top-card__company-name a, .topcard__org-name-link"
  );

  const locationEl = document.querySelector<HTMLElement>(
    ".job-details-jobs-unified-top-card__primary-description-without-tagline .tvm__text, .topcard__flavor--bullet"
  );

  const locationText = locationEl?.innerText?.trim() ?? "";

  return {
    platform: "linkedin",
    company: companyEl?.innerText?.trim() ?? "",
    title: titleEl?.innerText?.trim() ?? "",
    location: locationText,
    isRemote: /remote/i.test(locationText),
  };
};
