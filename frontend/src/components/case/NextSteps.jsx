import Card from "../Card.jsx";
import CopyButton from "../CopyButton.jsx";

function checklistAsText(checklist) {
  const lines = [];
  for (const item of checklist) {
    lines.push(`- ${item.what_to_add} (${item.policy_section || "policy"}: ${item.requirement})`);
  }
  return lines.join("\n");
}

export default function NextSteps({ caseDetail }) {
  if (caseDetail.missing_info_checklist.length > 0) {
    const checklist = caseDetail.missing_info_checklist;
    return (
      <Card title="Add before sending" actions={<CopyButton text={checklistAsText(checklist)} />}>
        <ul className="space-y-2">
          {checklist.map((item, index) => (
            <li key={index} className="text-sm">
              <span className="font-medium">{item.what_to_add}</span>
              <span className="block text-xs text-slate-500">
                For: {item.requirement}
                {item.policy_section && ` · ${item.policy_section}`}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    );
  }

  if (caseDetail.appeal_letter) {
    return (
      <Card title="Draft appeal letter" actions={<CopyButton text={caseDetail.appeal_letter} />}>
        <p className="mb-2 text-xs text-slate-500">
          Draft only. Fill in the [ADD: ...] parts and check every statement before sending.
        </p>
        <pre className="whitespace-pre-wrap rounded bg-slate-50 p-3 font-sans text-sm">
          {caseDetail.appeal_letter}
        </pre>
      </Card>
    );
  }
  return null;
}
