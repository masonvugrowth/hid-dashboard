/**
 * Canonical Target Audience values — shared across all pages.
 * Must match the TEXT[] enum enforced by the backend.
 */
export const AUDIENCES = [
  "Solo",
  "Couple",
  "Friend Group",
  "Family",
  "Business",
  "Digital Nomad",
  "High Intent",
  "Generic",
];

/** Color mapping for TA badges / pills */
export const TA_COLORS = {
  Solo:            { bg: "bg-teal-50",    text: "text-teal-700",    border: "border-teal-200" },
  Couple:          { bg: "bg-pink-50",    text: "text-pink-700",    border: "border-pink-200" },
  "Friend Group":  { bg: "bg-amber-50",   text: "text-amber-700",   border: "border-amber-200" },
  Family:          { bg: "bg-green-50",   text: "text-green-700",   border: "border-green-200" },
  Business:        { bg: "bg-blue-50",    text: "text-blue-700",    border: "border-blue-200" },
  "Digital Nomad": { bg: "bg-purple-50",  text: "text-purple-700",  border: "border-purple-200" },
  "High Intent":   { bg: "bg-red-50",     text: "text-red-700",     border: "border-red-200" },
  Generic:         { bg: "bg-gray-50",    text: "text-gray-600",    border: "border-gray-200" },
};

/** Get Tailwind classes for a TA pill */
export function getTAClasses(ta) {
  const c = TA_COLORS[ta];
  if (!c) return { bg: "bg-gray-50", text: "text-gray-600", border: "border-gray-200" };
  return c;
}
