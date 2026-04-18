"use client";

import { useRouter } from "next/navigation";

import { logoutRequest, type CurrentUser } from "@/lib/auth";

export function UserMenu({ user }: { user: CurrentUser | null }) {
  const router = useRouter();
  if (!user) return null;

  async function onLogout() {
    await logoutRequest();
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex items-center gap-2 text-xs text-warm-fog/80">
      <span>{user.display_name}</span>
      <button onClick={onLogout} className="rounded bg-warm-fog/10 px-2 py-1 hover:bg-warm-fog/20">
        Sign out
      </button>
    </div>
  );
}
