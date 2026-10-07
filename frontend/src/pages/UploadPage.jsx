import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadCase } from "../api.js";
import Card from "../components/Card.jsx";
import DecisionSupportNotice from "../components/DecisionSupportNotice.jsx";

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;

export default function UploadPage() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const navigate = useNavigate();

  function chooseFile(event) {
    const file = event.target.files[0];
    setErrorMessage("");
    if (!file) {
      setSelectedFile(null);
      return;
    }
    // Checked again on the server; checking here just gives faster feedback.
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setErrorMessage("Please choose a PDF file.");
      return;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setErrorMessage("The file is larger than 10 MB.");
      return;
    }
    setSelectedFile(file);
  }

  async function submitFile(event) {
    event.preventDefault();
    setIsUploading(true);
    setErrorMessage("");
    try {
      const createdCase = await uploadCase(selectedFile);
      navigate(`/cases/${createdCase.case_id}`);
    } catch (error) {
      setErrorMessage(error.message);
      setIsUploading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Check a request before you send it</h1>
        <p className="mt-1 text-slate-600">
          Upload a prior-authorization request for a lumbar spine MRI. ClaimGuard hides patient
          details, compares the request with the coverage policy, and shows the evidence.
        </p>
      </div>
      <DecisionSupportNotice />
      <Card>
        <form onSubmit={submitFile} className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Request PDF (max 10 MB)</span>
            <input
              type="file"
              accept="application/pdf,.pdf"
              onChange={chooseFile}
              className="mt-2 block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-white"
            />
          </label>
          {errorMessage && <p className="text-sm text-rose-700">{errorMessage}</p>}
          <button
            type="submit"
            disabled={!selectedFile || isUploading}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            {isUploading ? "Uploading..." : "Check request"}
          </button>
        </form>
      </Card>
      <p className="text-xs text-slate-500">
        Try one of the synthetic requests in <code>data/evaluation/cases/</code>. Do not upload real
        patient documents to this demo.
      </p>
    </div>
  );
}
