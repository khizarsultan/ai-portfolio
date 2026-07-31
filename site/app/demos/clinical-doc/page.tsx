import DemoPage from "@/components/demo/DemoPage";
import ClinicalDocDemo from "@/components/demo/ClinicalDocDemo";

export const metadata = { title: "Clinical Documentation Agent — Live Demo — Khizar Sultan" };

export default function Page() {
  return (
    <DemoPage slug="clinical-documentation-agent">
      <ClinicalDocDemo />
    </DemoPage>
  );
}
