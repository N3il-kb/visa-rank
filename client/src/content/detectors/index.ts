import type { JobInfo } from "../../lib/types";
import { isWorkday, extractWorkday } from "./workday";
import { isGreenhouse, extractGreenhouse } from "./greenhouse";
import { isLever, extractLever } from "./lever";
import { isLinkedIn, extractLinkedIn } from "./linkedin";
import { isIcims, extractIcims } from "./icims";
import { isPhenom, isPhenomHost, extractPhenom } from "./phenom";
import { isAvature, extractAvature } from "./avature";

export const detectJob = (): JobInfo | null => {
  let partial: Partial<JobInfo> | null = null;

  if (isWorkday()) partial = extractWorkday();
  else if (isGreenhouse()) partial = extractGreenhouse();
  else if (isLever()) partial = extractLever();
  else if (isLinkedIn()) partial = extractLinkedIn();
  else if (isIcims()) partial = extractIcims();
  // Avature before Phenom — Avature uses a reliable meta tag, no ambiguity.
  else if (isAvature()) partial = extractAvature();
  else if (isPhenomHost() || isPhenom()) partial = extractPhenom();

  if (!partial) return null;

  return {
    company: partial.company ?? "",
    title: partial.title ?? "",
    location: partial.location ?? "",
    isRemote: partial.isRemote ?? false,
    platform: partial.platform ?? "unknown",
    url: location.href,
    description: partial.description ?? "",
  };
};
