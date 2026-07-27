import Link from "next/link";
import { Project, demoLink } from "@/lib/projects";

const DOMAIN_STYLES: Record<Project["domain"], string> = {
  Healthcare: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  Cybersecurity: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  Finance: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
};

export default function ProjectCard({ project }: { project: Project }) {
  const link = demoLink(project);
  return (
    <div className="group flex flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-3 flex items-center gap-2">
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${DOMAIN_STYLES[project.domain]}`}>
          {project.domain}
        </span>
        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {project.kind}
        </span>
        {project.featured && (
          <span className="rounded-full bg-brand/10 px-2.5 py-0.5 text-xs font-semibold text-brand">
            Flagship
          </span>
        )}
      </div>

      <h3 className="text-lg font-semibold tracking-tight">{project.title}</h3>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{project.tagline}</p>

      <div className="mt-4 flex flex-wrap gap-1.5">
        {project.stack.slice(0, 4).map((s) => (
          <span key={s} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            {s}
          </span>
        ))}
      </div>

      <div className="mt-6 flex items-center gap-3 pt-2">
        {link ? (
          link.internal ? (
            <Link
              href={link.href}
              className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-light"
            >
              Live demo →
            </Link>
          ) : (
            <a
              href={link.href}
              target="_blank"
              rel="noreferrer"
              className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-light"
            >
              Live demo ↗
            </a>
          )
        ) : (
          <span className="rounded-lg border border-dashed border-slate-300 px-4 py-2 text-sm text-slate-400 dark:border-slate-700">
            Demo coming soon
          </span>
        )}
        <Link
          href={`/projects/${project.slug}`}
          className="text-sm font-medium text-brand hover:underline"
        >
          Details →
        </Link>
      </div>
    </div>
  );
}
