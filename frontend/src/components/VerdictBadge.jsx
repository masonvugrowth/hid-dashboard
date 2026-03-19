const STYLES = {
  winning:        "bg-green-600 text-white",
  good:           "bg-blue-500 text-white",
  neutral:        "bg-gray-400 text-white",
  underperformer: "bg-amber-500 text-white",
  kill:           "bg-red-600 text-white",
};

export default function VerdictBadge({ verdict, derived, className = "" }) {
  if (!verdict) return <span className="text-gray-300 text-xs">—</span>;
  const style = STYLES[verdict] || "bg-gray-300 text-gray-600";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${style} ${className}`}>
      {verdict}
      {derived && <span className="opacity-70 text-[10px]">(derived)</span>}
    </span>
  );
}
