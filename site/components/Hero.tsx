export default function Hero() {
  return (
    <section className="mx-auto max-w-6xl px-6 pt-16 pb-10">
      <p className="mb-3 text-sm font-medium uppercase tracking-widest text-brand">
        Khizar Sultan · AI &amp; ML
      </p>
      <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
        Live AI &amp; machine-learning projects you can actually try.
      </h1>
      <p className="mt-5 max-w-2xl text-lg text-slate-600 dark:text-slate-300">
        A working showcase across healthcare, cybersecurity, and finance — from a multi-agent
        prior-authorization system to production-style ML classifiers. Not just code: every
        project has a live, interactive demo.
      </p>
      <div className="mt-8 flex gap-3">
        <a
          href="#projects"
          className="rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-light"
        >
          Explore projects
        </a>
      </div>
    </section>
  );
}
