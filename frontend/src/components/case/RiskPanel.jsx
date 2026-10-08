import Card from "../Card.jsx";
import { formatPercent } from "../../labels.js";

export default function RiskPanel({ caseDetail }) {
  if (caseDetail.denial_probability === null) {
    return (
      <Card title="Denial risk model">
        <p className="text-sm text-slate-500">No risk score for this case.</p>
      </Card>
    );
  }
  const riskPercent = Math.round(caseDetail.denial_probability * 100);
  let barColor = "bg-emerald-500";
  if (riskPercent >= 50) {
    barColor = "bg-rose-500";
  } else if (riskPercent >= 30) {
    barColor = "bg-amber-500";
  }

  return (
    <Card title="Denial risk model">
      <p className="text-3xl font-semibold">{formatPercent(caseDetail.denial_probability)}</p>
      <div className="mt-2 h-2 w-full rounded bg-slate-100">
        <div className={`h-2 rounded ${barColor}`} style={{ width: `${riskPercent}%` }} />
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {caseDetail.risk_model_type} trained on synthetic data
      </p>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
        {caseDetail.risk_reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </Card>
  );
}
