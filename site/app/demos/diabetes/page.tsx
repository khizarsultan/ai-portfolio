import DemoPage from "@/components/demo/DemoPage";
import DiabetesDemo from "@/components/demo/DiabetesDemo";

export const metadata = { title: "Diabetes Prediction — Live Demo — Khizar Sultan" };

export default function Page() {
  return (
    <DemoPage slug="diabetes-prediction">
      <DiabetesDemo />
    </DemoPage>
  );
}
