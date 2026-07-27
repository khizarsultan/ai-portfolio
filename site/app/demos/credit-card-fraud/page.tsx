import DemoPage from "@/components/demo/DemoPage";
import FraudDemo from "@/components/demo/FraudDemo";

export const metadata = { title: "Credit Card Fraud Detection — Live Demo — Khizar Sultan" };

export default function Page() {
  return (
    <DemoPage slug="credit-card-fraud-detection">
      <FraudDemo />
    </DemoPage>
  );
}
