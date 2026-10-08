import { useState } from "react";
import { reviewCase } from "../../api.js";
import { VERDICT_NAMES } from "../../labels.js";
import Card from "../Card.jsx";
import VerdictBadge from "../VerdictBadge.jsx";

export default function ReviewForm({ caseDetail, onReviewed }) {
  const [reviewerName, setReviewerName] = useState("");
  const [isOverriding, setIsOverriding] = useState(caseDetail.verdict === null);
  const [finalVerdict, setFinalVerdict] = useState("missing_information");
  const [reason, setReason] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  async function submitReview(event) {
    event.preventDefault();
    setErrorMessage("");
    const review = { reviewer_name: reviewerName, decision: isOverriding ? "override" : "accept" };
    if (isOverriding) {
      review.final_verdict = finalVerdict;
      review.reason = reason;
    }
    try {
      onReviewed(await reviewCase(caseDetail.case_id, review));
    } catch (error) {
      setErrorMessage(error.message);
    }
  }

  if (caseDetail.final_verdict) {
    return (
      <Card title="Reviewer decision">
        <VerdictBadge verdict={caseDetail.final_verdict} size="large" />
        <p className="mt-2 text-sm text-slate-600">
          {caseDetail.reviewer_decision === "accept" ? "Accepted" : "Overridden"} by{" "}
          {caseDetail.reviewer_name}
        </p>
        {caseDetail.reviewer_reason && <p className="mt-1 text-sm">{caseDetail.reviewer_reason}</p>}
      </Card>
    );
  }

  return (
    <Card title="Your decision">
      <form onSubmit={submitReview} className="space-y-3 text-sm">
        <input
          required
          value={reviewerName}
          onChange={(event) => setReviewerName(event.target.value)}
          placeholder="Your name"
          className="w-full rounded-md border border-slate-300 px-3 py-2"
        />
        {caseDetail.verdict && (
          <div className="flex gap-4">
            <label className="flex items-center gap-2">
              <input type="radio" checked={!isOverriding} onChange={() => setIsOverriding(false)} />
              Accept suggestion
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" checked={isOverriding} onChange={() => setIsOverriding(true)} />
              Override
            </label>
          </div>
        )}
        {isOverriding && (
          <>
            <select
              value={finalVerdict}
              onChange={(event) => setFinalVerdict(event.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2"
            >
              {Object.entries(VERDICT_NAMES).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            <textarea
              required
              minLength={10}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Why are you overriding? (required)"
              className="h-20 w-full rounded-md border border-slate-300 px-3 py-2"
            />
          </>
        )}
        {errorMessage && <p className="text-rose-700">{errorMessage}</p>}
        <button type="submit" className="rounded-md bg-slate-900 px-4 py-2 font-medium text-white">
          Save decision
        </button>
      </form>
    </Card>
  );
}
