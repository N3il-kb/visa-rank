import type { WorkAuthFieldType } from "../lib/types";

// ATS-safe answers that are truthful but avoid triggering auto-reject filters.
const AUTOFILL_ANSWERS: Record<WorkAuthFieldType, string> = {
  authorized: "Yes",
  // Framing: accurate (you will need future sponsorship) but avoids the
  // phrasing some ATS use to hard-filter candidates.
  sponsorship: "Yes, I will require sponsorship",
  visa_type: "F-1 OPT",
};

const findInputForLabel = (labelText: RegExp): HTMLInputElement | null => {
  for (const label of Array.from(document.querySelectorAll<HTMLLabelElement>("label"))) {
    if (labelText.test(label.innerText)) {
      const input =
        label.querySelector<HTMLInputElement>("input") ??
        document.getElementById(label.htmlFor ?? "") as HTMLInputElement | null;
      if (input) return input;
    }
  }
  return null;
};

const setNativeValue = (el: HTMLInputElement, value: string) => {
  const nativeInputSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value"
  )?.set;
  nativeInputSetter?.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
};

export const autofillField = (fieldType: WorkAuthFieldType): boolean => {
  const patterns: Record<WorkAuthFieldType, RegExp> = {
    authorized: /authorized to work/i,
    sponsorship: /require.*sponsor|sponsor.*required/i,
    visa_type: /visa type|work authorization type/i,
  };

  const answer = AUTOFILL_ANSWERS[fieldType];
  const input = findInputForLabel(patterns[fieldType]);

  if (!input) return false;

  if (input.type === "radio" || input.type === "checkbox") {
    // Find the radio/checkbox whose label matches the answer
    const container = input.closest("fieldset") ?? input.parentElement;
    const options = container?.querySelectorAll<HTMLInputElement>(`input[type="${input.type}"]`);
    for (const opt of Array.from(options ?? [])) {
      const lbl = document.querySelector<HTMLLabelElement>(`label[for="${opt.id}"]`);
      if (lbl && new RegExp(answer, "i").test(lbl.innerText)) {
        opt.click();
        return true;
      }
    }
    return false;
  }

  setNativeValue(input, answer);
  return true;
};
