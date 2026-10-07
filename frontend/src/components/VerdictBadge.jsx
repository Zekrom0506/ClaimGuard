import { VERDICT_COLORS, VERDICT_NAMES } from "../labels.js";

export default function VerdictBadge({ verdict, size = "small" }) {
  if (!verdict) {
    return <span className="text-sm text-slate-400">—</span>;
  }
  const sizeClasses = size === "large" ? "px-3 py-1 text-base" : "px-2 py-0.5 text-xs";
  return (
    <span className={`inline-block rounded-full font-medium ring-1 ${sizeClasses} ${VERDICT_COLORS[verdict]}`}>
      {VERDICT_NAMES[verdict]}
    </span>
  );
}
