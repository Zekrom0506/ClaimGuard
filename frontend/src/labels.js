// Human-readable names for values that come from the API.

export const VERDICT_NAMES = {
  likely_approved: "Likely approved",
  missing_information: "Missing information",
  likely_denied: "Likely denied",
};

export const VERDICT_COLORS = {
  likely_approved: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  missing_information: "bg-amber-50 text-amber-800 ring-amber-200",
  likely_denied: "bg-rose-50 text-rose-800 ring-rose-200",
};

export const STATUS_NAMES = {
  queued: "Queued",
  processing: "Processing",
  done: "Ready for review",
  needs_human_review: "Needs human review",
  failed: "Failed",
};

export const FLAG_NAMES = {
  extraction_invalid: "The AI could not read the request reliably",
  no_policy_found: "No matching policy text was found",
  citation_failed: "Some AI citations failed the check and were removed",
  no_valid_citations: "No AI citation could be verified",
  verdict_inconsistent_with_requirements: "The verdict contradicts its own requirement list",
  verdict_invalid: "The AI did not return a usable verdict",
  possible_prompt_injection: "The document contains text that tries to instruct the AI",
  ai_and_risk_model_disagree: "The AI and the risk model disagree",
  risk_model_unavailable: "Risk model not loaded",
  appeal_letter_failed: "The appeal letter could not be drafted",
};

export function describeFlag(flag) {
  if (flag.startsWith("extraction_source_not_found:")) {
    const fieldName = flag.split(":")[1].replaceAll("_", " ");
    return `Source sentence for "${fieldName}" was not found in the document`;
  }
  return FLAG_NAMES[flag] || flag;
}

export function formatPercent(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${Math.round(value * 1000) / 10}%`;
}
