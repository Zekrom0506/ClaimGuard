import Card from "../Card.jsx";

const FIELD_NAMES = {
  patient_age: "Patient age",
  procedure_code: "CPT code",
  diagnosis_codes: "Diagnosis codes",
  symptom_duration_weeks: "Symptom duration (weeks)",
  physical_therapy_weeks: "Physical therapy (weeks)",
  other_conservative_treatments: "Other treatments",
  red_flags: "Red flags",
  neurological_exam_documented: "Neurological exam documented",
  prior_lumbar_mri_within_12_months: "Lumbar MRI in last 12 months",
  requesting_specialty: "Requesting specialty",
};

function formatValue(value) {
  if (value === null || value === undefined) {
    return <span className="text-slate-400">Not stated</span>;
  }
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : <span className="text-slate-400">None</span>;
  }
  if (value === true) {
    return "Yes";
  }
  if (value === false) {
    return "No";
  }
  return String(value);
}

export default function ExtractedFields({ extractedFields }) {
  if (!extractedFields) {
    return null;
  }
  return (
    <Card title="Extracted facts">
      <p className="mb-3 text-sm text-slate-600">{extractedFields.clinical_summary}</p>
      <dl className="divide-y divide-slate-100">
        {Object.entries(FIELD_NAMES).map(([fieldName, label]) => {
          const field = extractedFields[fieldName];
          return (
            <div key={fieldName} className="grid gap-1 py-2 sm:grid-cols-3">
              <dt className="text-sm text-slate-500">{label}</dt>
              <dd className="text-sm font-medium sm:col-span-2">
                {formatValue(field?.value)}
                {field?.source_sentence && (
                  <p className="mt-0.5 text-xs font-normal italic text-slate-500">
                    “{field.source_sentence}”
                  </p>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
    </Card>
  );
}
