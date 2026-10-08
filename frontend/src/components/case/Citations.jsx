import { useState } from "react";
import Card from "../Card.jsx";

function Citation({ citation }) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <li className="rounded-md border border-slate-200">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
      >
        <span className="block font-medium text-slate-800">
          {citation.section_title} · page {citation.page_number}
        </span>
        <span className="block text-slate-600">“{citation.quote}”</span>
        <span className="mt-1 block text-xs text-sky-700">
          {isOpen ? "Hide policy text" : "Show policy text"}
        </span>
      </button>
      {isOpen && (
        <p className="border-t border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-700">
          <span className="mb-1 block font-semibold">{citation.policy_name}</span>
          {citation.chunk_text}
        </p>
      )}
    </li>
  );
}

export default function Citations({ citations, failedCitations }) {
  return (
    <Card title="Policy evidence (checked)">
      {citations.length === 0 && (
        <p className="text-sm text-slate-500">No citation could be verified.</p>
      )}
      <ul className="space-y-2">
        {citations.map((citation, index) => (
          <Citation key={index} citation={citation} />
        ))}
      </ul>
      {failedCitations.length > 0 && (
        <p className="mt-3 text-xs text-rose-700">
          {failedCitations.length} citation(s) from the AI did not match the policy text and were
          removed.
        </p>
      )}
    </Card>
  );
}
