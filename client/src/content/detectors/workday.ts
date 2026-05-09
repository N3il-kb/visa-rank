import type { JobInfo } from "../../lib/types";

const toTitleCase = (s: string): string =>
  s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const isWorkday = (): boolean =>
  location.hostname.endsWith(".myworkdayjobs.com");

// Workday URLs embed location + title in the path:
// /{locale}/{tenant}/job/{location-slug}/{title-slug}/apply/...
const parseFromUrl = (): { title: string; location: string } => {
  const parts = location.pathname.split("/").filter(Boolean);
  const jobIdx = parts.indexOf("job");
  if (jobIdx === -1 || jobIdx + 2 >= parts.length) return { title: "", location: "" };

  const rawLocation = decodeURIComponent(parts[jobIdx + 1]);
  // "PA---Philadelphia,-1701-John-F-Kennedy-Blvd" → "PA - Philadelphia, 1701 John F Kennedy Blvd"
  const location_ = rawLocation.replace(/---/g, " - ").replace(/-/g, " ").replace(/\s+/g, " ").trim();

  const rawTitle = parts[jobIdx + 2];
  // "Comcast-Product-Management-Shield-Co-op_R435874" → "Comcast Product Management Shield Co Op"
  const title = toTitleCase(rawTitle.replace(/_[A-Z]\d+$/, ""));

  return { title, location: location_ };
};

export const extractWorkday = (): Partial<JobInfo> => {
  const company = location.hostname.split(".")[0];

  const titleEl =
    document.querySelector<HTMLElement>('[data-automation-id="jobPostingHeader"]') ??
    document.querySelector<HTMLElement>("h1");

  const locationEl = document.querySelector<HTMLElement>('[data-automation-id="locations"]');

  const descEl =
    document.querySelector<HTMLElement>('[data-automation-id="jobPostingDescription"]') ??
    document.querySelector<HTMLElement>('[data-automation-id="richTextEditor"]');

  // JSON-LD is server-rendered in <head> — available immediately before React hydrates.
  const getJsonLdDescription = (): string => {
    try {
      const el = document.querySelector<HTMLScriptElement>('script[type="application/ld+json"]');
      const data = JSON.parse(el?.textContent ?? "{}");
      return typeof data.description === "string" ? data.description : "";
    } catch {
      return "";
    }
  };

  const urlFallback = parseFromUrl();
  const locationText = locationEl?.innerText?.trim() || urlFallback.location;

  return {
    platform: "workday",
    company: toTitleCase(company),
    title: titleEl?.innerText?.trim() || urlFallback.title,
    location: locationText,
    isRemote: /remote/i.test(locationText),
    description: descEl?.innerText?.trim() || getJsonLdDescription(),
  };
};
