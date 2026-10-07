import { STATUS_NAMES } from "../labels.js";

const STATUS_COLORS = {
  queued: "bg-slate-100 text-slate-700",
  processing: "bg-sky-100 text-sky-800",
  done: "bg-emerald-100 text-emerald-800",
  needs_human_review: "bg-amber-100 text-amber-800",
  failed: "bg-rose-100 text-rose-800",
};

export default function StatusBadge({ status }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[status] || ""}`}>
      {STATUS_NAMES[status] || status}
    </span>
  );
}
