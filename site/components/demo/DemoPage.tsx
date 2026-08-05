import Link from "next/link";
import { ReactNode } from "react";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { getProject } from "@/lib/projects";

// Server-rendered chrome shared by every demo route (Nav, header, back link, Footer).
// The interactive island is passed as `children` (a client component).
export default function DemoPage({ slug, wide, children }: { slug: string; wide?: boolean; children: ReactNode }) {
  const p = getProject(slug);
  return (
    <>
      <Nav />
      <main className={`mx-auto ${wide ? "max-w-7xl" : "max-w-5xl"} px-6 py-12`}>
        <Link href={`/projects/${slug}`} className="text-sm text-slate-500 hover:text-brand">
          ← {p ? p.title : "Project"}
        </Link>
        {p && (
          <>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">{p.domain}</span>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">{p.kind}</span>
              <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">● Live</span>
            </div>
            <h1 className="mt-3 text-3xl font-bold tracking-tight">{p.title}</h1>
            <p className="mt-2 text-lg text-slate-600 dark:text-slate-300">{p.tagline}</p>
          </>
        )}
        <div className="mt-8">{children}</div>
      </main>
      <Footer />
    </>
  );
}
