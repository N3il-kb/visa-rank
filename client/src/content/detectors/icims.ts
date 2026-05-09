import type { JobInfo } from "../../lib/types";

const toTitleCase = (s: string): string =>
  s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const companyFromSubdomain = (): string => {
  const sub = location.hostname.replace(/\.icims\.com$/, "");
  const stripped = sub.replace(/^(university|jobs|careers|recruiting|talent|apply|hire)-/i, "");
  return toTitleCase(stripped);
};

// iCIMS title format: "Job Title in Location, State | Careers at ..."
const parseTitleFromDocTitle = (): { title: string; location: string } => {
  const raw = document.title;
  const pipeIdx = raw.indexOf(" | ");
  const relevant = pipeIdx > -1 ? raw.slice(0, pipeIdx) : raw;
  const inIdx = relevant.lastIndexOf(" in ");
  if (inIdx > -1) {
    return {
      title: relevant.slice(0, inIdx).trim(),
      location: relevant.slice(inIdx + 4).trim(),
    };
  }
  return { title: relevant.trim(), location: "" };
};

export const isIcims = (): boolean => {
  if (!location.hostname.endsWith(".icims.com")) return false;
  if (!/\/jobs\/\d+\//.test(location.pathname)) return false;
  // Skip the outer wrapper page — only parse inside the in_iframe version
  // where the actual job DOM is rendered.
  const params = new URLSearchParams(location.search);
  return params.get("in_iframe") === "1";
};

export const extractIcims = (): Partial<JobInfo> => {
  const company = companyFromSubdomain();
  const { title, location: locationFromTitle } = parseTitleFromDocTitle();

  const descEl =
    document.querySelector<HTMLElement>('[class*="iCIMS_JobContent"]') ??
    document.querySelector<HTMLElement>('[id*="JobContent"]') ??
    document.querySelector<HTMLElement>('[class*="iCIMS_InfoMsg"]');

  const locationEl =
    document.querySelector<HTMLElement>('[class*="iCIMS_JobHeaderField"]') ??
    document.querySelector<HTMLElement>('[id*="Location"] span');

  const locationText = locationEl?.innerText?.trim() || locationFromTitle;

  return {
    platform: "icims",
    company,
    title,
    location: locationText,
    isRemote: /remote/i.test(locationText),
    description: descEl?.innerText?.trim() ?? "",
  };
};
