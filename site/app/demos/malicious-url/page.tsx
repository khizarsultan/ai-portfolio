import DemoPage from "@/components/demo/DemoPage";
import MaliciousUrlDemo from "@/components/demo/MaliciousUrlDemo";

export const metadata = { title: "Malicious URL Detection — Live Demo — Khizar Sultan" };

export default function Page() {
  return (
    <DemoPage slug="malicious-url-detection">
      <MaliciousUrlDemo />
    </DemoPage>
  );
}
