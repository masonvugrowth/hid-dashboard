/**
 * CountryBadge — Hot / Warm / Cold tier badge.
 */
const TIER_STYLES = {
  Hot:  "bg-red-100 text-red-700 border border-red-200",
  Warm: "bg-amber-100 text-amber-700 border border-amber-200",
  Cold: "bg-blue-100 text-blue-600 border border-blue-200",
};

const TIER_DOTS = {
  Hot:  "bg-red-500",
  Warm: "bg-amber-400",
  Cold: "bg-blue-400",
};

export default function CountryBadge({ tier }) {
  const style = TIER_STYLES[tier] || "bg-gray-100 text-gray-500";
  const dot   = TIER_DOTS[tier]   || "bg-gray-400";

  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${style}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {tier}
    </span>
  );
}
