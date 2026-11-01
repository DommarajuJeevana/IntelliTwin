export default function EmptyState({ title, hint }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-ink-600 py-12 text-center">
      <p className="text-text font-medium">{title}</p>
      {hint ? <p className="mt-1 text-sm text-text-dim">{hint}</p> : null}
    </div>
  );
}
