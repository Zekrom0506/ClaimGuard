import { useState } from "react";

export default function CopyButton({ text }) {
  const [wasCopied, setWasCopied] = useState(false);

  async function copyText() {
    await navigator.clipboard.writeText(text);
    setWasCopied(true);
    setTimeout(() => setWasCopied(false), 2000);
  }

  return (
    <button
      type="button"
      onClick={copyText}
      className="rounded-md border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-slate-100"
    >
      {wasCopied ? "Copied" : "Copy"}
    </button>
  );
}
