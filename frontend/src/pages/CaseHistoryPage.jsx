import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listCases } from "../api.js";
import StatusBadge from "../components/StatusBadge.jsx";
import SyntheticDataBadge from "../components/SyntheticDataBadge.jsx";
import VerdictBadge from "../components/VerdictBadge.jsx";
import { formatPercent } from "../labels.js";

export default function CaseHistoryPage() {
  const [cases, setCases] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    listCases().then(setCases).catch((error) => setErrorMessage(error.message));
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Case history</h1>
        <SyntheticDataBadge />
      </div>
      {errorMessage && <p className="text-sm text-rose-700">{errorMessage}</p>}
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">File</th>
              <th className="px-4 py-2">Uploaded</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">AI suggestion</th>
              <th className="px-4 py-2">Denial risk</th>
              <th className="px-4 py-2">Final decision</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((caseRow) => (
              <tr key={caseRow.case_id} className="border-b border-slate-100 last:border-0">
                <td className="px-4 py-2">
                  <Link to={`/cases/${caseRow.case_id}`} className="font-medium text-sky-700 hover:underline">
                    {caseRow.original_filename}
                  </Link>
                  {caseRow.model_disagreement && (
                    <span className="ml-2 text-xs text-amber-700">models disagree</span>
                  )}
                </td>
                <td className="px-4 py-2 text-slate-600">
                  {new Date(caseRow.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2"><StatusBadge status={caseRow.status} /></td>
                <td className="px-4 py-2"><VerdictBadge verdict={caseRow.verdict} /></td>
                <td className="px-4 py-2">{formatPercent(caseRow.denial_probability)}</td>
                <td className="px-4 py-2"><VerdictBadge verdict={caseRow.final_verdict} /></td>
              </tr>
            ))}
            {cases.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  No cases yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
