import Card from "../Card.jsx";
import VerdictBadge from "../VerdictBadge.jsx";

const STATUS_STYLES = {
  met: "text-emerald-700",
  not_met: "text-rose-700",
  unclear: "text-amber-700",
};
const STATUS_NAMES = { met: "Met", not_met: "Not met", unclear: "Unclear" };

export default function VerdictPanel({ caseDetail }) {
  return (
    <Card title="AI suggestion">
      <div className="space-y-3">
        <VerdictBadge verdict={caseDetail.verdict} size="large" />
        {caseDetail.verdict_reason && <p className="text-sm">{caseDetail.verdict_reason}</p>}
        {caseDetail.requirement_checks.length > 0 && (
          <ul className="space-y-1">
            {caseDetail.requirement_checks.map((requirementCheck, index) => (
              <li key={index} className="flex gap-2 text-sm">
                <span className={`w-16 shrink-0 font-medium ${STATUS_STYLES[requirementCheck.status]}`}>
                  {STATUS_NAMES[requirementCheck.status]}
                </span>
                <span>{requirementCheck.requirement}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
