import { redirect } from "next/navigation";

export default function SettingsRoot() {
  redirect("/settings/log-forwarding");
}
