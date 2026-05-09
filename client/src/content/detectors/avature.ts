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

  // Description: collect all field values from the main article sections
  const descEls = document.querySelectorAll<HTMLElement>(
    ".grid__item--main .article__content__view__field__value"
  );
  const description = Array.from(descEls)
    .map((el) => el.innerText.trim())
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
