import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import Footer from "@/components/Footer";
import ProjectCard from "@/components/ProjectCard";
import { PROJECTS } from "@/lib/projects";

export default function Home() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <section id="projects" className="mx-auto max-w-6xl px-6 py-10">
          <h2 className="mb-6 text-2xl font-bold tracking-tight">Projects</h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-2">
            {PROJECTS.map((p) => (
              <ProjectCard key={p.slug} project={p} />
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
