import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getDashboardSummary } from "../api.js";
import Card from "../components/Card.jsx";
import SyntheticDataBadge from "../components/SyntheticDataBadge.jsx";
import { VERDICT_NAMES, formatPercent } from "../labels.js";

const BAR_COLORS = {
  likely_approved: "#059669",
  missing_information: "#d97706",
  likely_denied: "#e11d48",
};

function Statistic({ label, value, note }) {
  return (
    <Card>
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-3xl font-semibold tracking-tight">{value}</p>
      {note && <p className="mt-1 text-xs text-slate-400">{note}</p>}
    </Card>
  );
}

export default function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    getDashboardSummary().then(setSummary).catch((error) => setErrorMessage(error.message));
  }, []);

  if (errorMessage) {
    return <p className="text-sm text-rose-700">{errorMessage}</p>;
  }
  if (!summary) {
    return <p className="text-sm text-slate-500">Loading...</p>;
  }

  const chartRows = [];
  for (const verdict of Object.keys(VERDICT_NAMES)) {
    chartRows.push({ verdict, name: VERDICT_NAMES[verdict], count: summary.verdict_counts[verdict] });
  }

  let averageTime = "—";
  if (summary.average_processing_seconds !== null) {
    averageTime = `${summary.average_processing_seconds.toFixed(1)} s`;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <SyntheticDataBadge />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Statistic label="Cases checked" value={summary.total_cases} />
        <Statistic
          label="Verdict accuracy (latest evaluation)"
          value={formatPercent(summary.latest_verdict_accuracy)}
          note={summary.latest_evaluation_run_at ? `Run ${summary.latest_evaluation_run_at}, 40 synthetic cases` : "No evaluation run yet"}
        />
        <Statistic
          label="Reviewer override rate"
          value={formatPercent(summary.override_rate)}
          note={`${summary.reviewed_cases} reviewed`}
        />
        <Statistic label="Average processing time" value={averageTime} />
      </div>
      <Card title="AI suggestions by verdict">
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartRows} margin={{ top: 8, right: 8, bottom: 8, left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={96}>
                {chartRows.map((row) => (
                  <Cell key={row.verdict} fill={BAR_COLORS[row.verdict]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
