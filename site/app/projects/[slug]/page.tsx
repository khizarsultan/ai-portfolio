import Link from "next/link";
import { notFound } from "next/navigation";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { PROJECTS, getProject, demoLink } from "@/lib/projects";

export function generateStaticParams() {
  return PROJECTS.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const p = getProject(slug);
  return { title: p ? `${p.title} — Khizar Sultan` : "Khizar Sultan" };
}

export default async function ProjectDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const project = getProject(slug);
  if (!project) notFound();

  const link = demoLink(project);

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-4xl px-6 py-12">
        <Link href="/#projects" className="text-sm text-slate-500 hover:text-brand">
          ← All projects
        </Link>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {project.domain}
          </span>
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {project.kind}
          </span>
        </div>

        <h1 className="mt-3 text-3xl font-bold tracking-tight">{project.title}</h1>
        <p className="mt-2 text-lg text-slate-600 dark:text-slate-300">{project.tagline}</p>

        <div className="mt-6">
          {link ? (
            link.internal ? (
              <Link
                href={link.href}
                className="rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-light"
              >
                Try the live demo →
              </Link>
            ) : (
              <a
                href={link.href}
                target="_blank"
                rel="noreferrer"
                className="rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-light"
              >
                Open live demo ↗
              </a>
            )
          ) : (
            <span className="rounded-lg border border-dashed border-slate-300 px-5 py-2.5 text-sm text-slate-400 dark:border-slate-700">
              Live demo coming soon
            </span>
          )}
        </div>

        <p className="mt-8 leading-relaxed text-slate-700 dark:text-slate-300">{project.description}</p>

        <h2 className="mt-10 text-lg font-semibold">Highlights</h2>
        <ul className="mt-3 space-y-2">
          {project.highlights.map((h) => (
            <li key={h} className="flex gap-2 text-slate-700 dark:text-slate-300">
              <span className="mt-1 text-brand">▹</span>
              <span>{h}</span>
            </li>
          ))}
        </ul>

        <h2 className="mt-10 text-lg font-semibold">Stack</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {project.stack.map((s) => (
            <span key={s} className="rounded bg-slate-100 px-2.5 py-1 text-sm text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {s}
            </span>
          ))}
        </div>
      </main>
      <Footer />
    </>
  );
}
