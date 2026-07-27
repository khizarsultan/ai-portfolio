import Link from "next/link";

export default function Nav() {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/60 bg-slate-50/80 backdrop-blur dark:border-slate-800/60 dark:bg-slate-950/80">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-brand text-white">
            <span className="h-2.5 w-2.5 rounded-sm bg-white" />
          </span>
          <span>Khizar Sultan</span>
        </Link>
        <nav className="flex items-center gap-6 text-sm text-slate-600 dark:text-slate-300">
          <Link href="/#projects" className="hover:text-brand">Projects</Link>
          <a href="https://github.com/khizarsultan" target="_blank" rel="noreferrer" className="hover:text-brand">
            GitHub
          </a>
        </nav>
      </div>
    </header>
  );
}
