import DemoPage from "@/components/demo/DemoPage";
import PaAgentDemo from "@/components/demo/PaAgentDemo";

export const metadata = { title: "Prior Authorization Agent — Live Demo — Khizar Sultan" };

export default function Page() {
  return (
    <DemoPage slug="prior-authorization-agent">
      <PaAgentDemo />
    </DemoPage>
  );
}
