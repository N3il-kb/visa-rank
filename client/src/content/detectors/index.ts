import type { JobInfo } from "../../lib/types";
import { isWorkday, extractWorkday } from "./workday";
import { isGreenhouse, extractGreenhouse } from "./greenhouse";
import { isLever, extractLever } from "./lever";
import { isLinkedIn, extractLinkedIn } from "./linkedin";

export const detectJob = (): JobInfo | null => {
  let partial: Partial<JobInfo> | null = null;

  if (isWorkday()) partial = extractWorkday();
  else if (isGreenhouse()) partial = extractGreenhouse();
  else if (isLever()) partial = extractLever();
  else if (isLinkedIn()) partial = extractLinkedIn();

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
