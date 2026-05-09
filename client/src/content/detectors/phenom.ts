import type { JobInfo } from "../../lib/types";

// Phenom powers career sites on *.phenompeople.com and custom domains.
// Detection is DOM-based for custom-domain deployments.
const PHENOM_SIGNALS = [
  () => !!(window as Record<string, unknown>)["phenom"],
  () => !!(window as Record<string, unknown>)["__PHENOM_DATA__"],
  () => !!document.querySelector('[class*="phenom-"]'),
  () => !!document.querySelector('script[src*="phenom"]'),
  () => !!document.querySelector('meta[content*="phenompeople"]'),
];

export const isPhenom = (): boolean =>
  PHENOM_SIGNALS.some((check) => { try { return check(); } catch { return false; } });

export const isPhenomHost = (): boolean =>
  location.hostname.endsWith(".phenompeople.com");

const companyFromMeta = (): string =>
  document.querySelector<HTMLMetaElement>('meta[property="og:site_name"]')?.content?.trim() ??
  document.querySelector<HTMLMetaElement>('meta[name="application-name"]')?.content?.trim() ??
  "";

const companyFromTitle = (): string => {
  // Common Phenom title format: "Job Title | Company Careers" or "Company | Careers"
  const parts = document.title.split(/\s*[|–-]\s*/);
  return parts.length > 1 ? parts[parts.length - 1].replace(/\s*(careers|jobs)$/i, "").trim() : "";
};

export const extractPhenom = (): Partial<JobInfo> => {
  const titleEl =
    document.querySelector<HTMLElement>('[class*="job-title"] h1') ??
    document.querySelector<HTMLElement>('h1[class*="title"]') ??
    document.querySelector<HTMLElement>(".job-details h1") ??
    document.querySelector<HTMLElement>("h1");

  const locationEl =
    document.querySelector<HTMLElement>('[class*="job-location"]') ??
    document.querySelector<HTMLElement>('[class*="location"]') ??
    document.querySelector<HTMLElement>('[data-field="location"]');

  const descEl =
    document.querySelector<HTMLElement>('[class*="job-description"]') ??
    document.querySelector<HTMLElement>('[class*="description"]');

  const locationText = locationEl?.innerText?.trim() ?? "";

  const company =
    companyFromMeta() ||
    companyFromTitle() ||
    // phenompeople.com subdomain: acme.phenompeople.com -> "Acme"
    (location.hostname.endsWith(".phenompeople.com")
      ? location.hostname.split(".")[0].replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
      : "");

  return {
    platform: "phenom",
    company,
    title: titleEl?.innerText?.trim() ?? "",
    location: locationText,
    isRemote: /remote/i.test(locationText),
    description: descEl?.innerText?.trim() ?? "",
  };
};
