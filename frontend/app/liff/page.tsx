import type { Metadata } from "next";

import { LiffApp } from "../../components/liff/liff-app";

export const metadata: Metadata = {
  title: "HR Self Service",
};

export default function LiffPage() {
  return <LiffApp />;
}
