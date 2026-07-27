export default function Footer() {
  return (
    <footer className="mt-24 border-t border-slate-200/60 dark:border-slate-800/60">
      <div className="mx-auto max-w-6xl px-6 py-10 text-sm text-slate-500 dark:text-slate-400">
        <p>
          Built by <span className="font-medium text-slate-700 dark:text-slate-200">Khizar Sultan</span> ·
          AI &amp; ML portfolio. Demos run on synthetic / public data — no real PHI or PII.
        </p>
        <p className="mt-1">© {new Date().getFullYear()} Khizar Sultan. All rights reserved.</p>
      </div>
    </footer>
  );
}
