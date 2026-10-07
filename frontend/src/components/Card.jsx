export default function Card({ title, children, actions = null }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      {title && (
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}
