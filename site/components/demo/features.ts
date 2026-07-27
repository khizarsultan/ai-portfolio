// Turn a preprocessor feature name ("log__bmi", "cat__gender_Male", "num__V14")
// into something a human can read on the demo pages.
const PREFIX = /^(log|num|cat|bin|remainder)__/;

export function prettyFeature(name: string): string {
  let s = name.replace(PREFIX, "");
  s = s.replace(/_/g, " ").trim();
  // Keep short codes (V1..V28) upper-cased; title-case the rest lightly.
  if (/^v\d+$/i.test(s)) return s.toUpperCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}
