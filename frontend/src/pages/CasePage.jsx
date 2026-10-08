import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getCase } from "../api.js";
import Card from "../components/Card.jsx";
import DecisionSupportNotice from "../components/DecisionSupportNotice.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import Citations from "../components/case/Citations.jsx";
import ExtractedFields from "../components/case/ExtractedFields.jsx";
import NextSteps from "../components/case/NextSteps.jsx";
import ReviewForm from "../components/case/ReviewForm.jsx";
import RiskPanel from "../components/case/RiskPanel.jsx";
import VerdictPanel from "../components/case/VerdictPanel.jsx";
import { describeFlag } from "../labels.js";

const POLL_INTERVAL_MILLISECONDS = 1500;
const STILL_RUNNING = ["queued", "processing"];

export default function CasePage() {
  const { caseId } = useParams();
  const [caseDetail, setCaseDetail] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  // Processing happens in the background, so ask for the status every 1.5 s until it finishes.
  useEffect(() => {
    let timerId = null;
    let isStopped = false;

    async function loadCase() {
      try {
        const loadedCase = await getCase(caseId);
        if (isStopped) {
          return;
        }
        setCaseDetail(loadedCase);
        if (STILL_RUNNING.includes(loadedCase.status)) {
          timerId = setTimeout(loadCase, POLL_INTERVAL_MILLISECONDS);
        }
      } catch (error) {
        setErrorMessage(error.message);
      }
    }

    loadCase();
    return () => {
      isStopped = true;
      clearTimeout(timerId);
    };
  }, [caseId]);

  if (errorMessage) {
    return <p className="text-sm text-rose-700">{errorMessage}</p>;
  }
  if (!caseDetail) {
    return <p className="text-sm text-slate-500">Loading...</p>;
  }

  const isRunning = STILL_RUNNING.includes(caseDetail.status);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold tracking-tight">{caseDetail.original_filename}</h1>
        <StatusBadge status={caseDetail.status} />
      </div>
      <DecisionSupportNotice />

      {isRunning && (
        <Card>
          <p className="animate-pulse text-sm text-slate-600">
            Reading the document, hiding private details and checking it against the policy...
          </p>
        </Card>
      )}

      {caseDetail.status === "failed" && (
        <Card>
          <p className="text-sm text-rose-700">{caseDetail.error_message}</p>
        </Card>
      )}

      {caseDetail.model_disagreement && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <strong>The AI and the risk model disagree.</strong> Please look at this case closely.
        </div>
      )}

      {caseDetail.review_flags.length > 0 && (
        <Card title="Look closer">
          <ul className="list-disc space-y-1 pl-5 text-sm text-amber-900">
            {caseDetail.review_flags.map((flag) => (
              <li key={flag}>{describeFlag(flag)}</li>
            ))}
          </ul>
        </Card>
      )}

      {!isRunning && caseDetail.status !== "failed" && (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <VerdictPanel caseDetail={caseDetail} />
            <Citations
              citations={caseDetail.citations}
              failedCitations={caseDetail.failed_citations}
            />
            <NextSteps caseDetail={caseDetail} />
            <ExtractedFields extractedFields={caseDetail.extracted_fields} />
          </div>
          <div className="space-y-4">
            <RiskPanel caseDetail={caseDetail} />
            <ReviewForm caseDetail={caseDetail} onReviewed={setCaseDetail} />
            {caseDetail.llm_cost_usd !== null && (
              <p className="text-xs text-slate-400">
                {caseDetail.llm_model_name} · ${caseDetail.llm_cost_usd.toFixed(4)} ·{" "}
                {caseDetail.processing_seconds} s
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
