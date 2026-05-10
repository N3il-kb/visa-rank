import type { JobInfo } from "../../lib/types";

// Avature powers career sites on custom domains (careers.ibm.com, etc.)
// Reliable detection: meta name="avature.portal.page" is injected server-side.
export const isAvature = (): boolean =>
  !!document.querySelector('meta[name="avature.portal.page"]');

export const extractAvature = (): Partial<JobInfo> => {
  // Title lives in the banner h2, not an h1
  const titleEl = document.querySelector<HTMLElement>("h2.banner__text__title");

  // Location is a dedicated span with class card-item-location
  const locationEl = document.querySelector<HTMLElement>(".card-item-location");

  // Company comes from og:site_name — clean and reliable ("IBM")
  const company =
    document.querySelector<HTMLMetaElement>('meta[property="og:site_name"]')?.content?.trim() ?? "";

  // Description: grab text from every <article> on the page. Avature wraps
  // each panel (main job content + side panels like "Other Relevant Job
  // Details" where the no-sponsor text lives) in an <article>. Field-value
  // selectors miss free-form text blocks, so go one level up.
  const articles = document.querySelectorAll<HTMLElement>("article");
  const description = Array.from(articles)
    .map((el) => el.textContent?.replace(/\s+/g, " ").trim() ?? "")
    .filter(Boolean)
    .join("\n\n");

  const locationText = locationEl?.innerText?.trim() ?? "";

  return {
    platform: "avature",
    company,
    title: titleEl?.innerText?.trim() ?? "",
    location: locationText,
    isRemote: /remote/i.test(locationText),
    description,
  };
};
