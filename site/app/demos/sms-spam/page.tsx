import DemoPage from "@/components/demo/DemoPage";
import SmsSpamDemo from "@/components/demo/SmsSpamDemo";

export const metadata = { title: "SMS Spam Detection — Live Demo — Khizar Sultan" };

export default function Page() {
  return (
    <DemoPage slug="sms-spam-detection">
      <SmsSpamDemo />
    </DemoPage>
  );
}
