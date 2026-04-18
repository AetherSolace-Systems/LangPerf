import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { fetchMode, fetchMe } from "@/lib/auth";
import { LoginForm } from "@/components/auth/login-form";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  const cookie = headers().get("cookie") ?? undefined;
  const [mode, me] = await Promise.all([fetchMode(), fetchMe(cookie)]);
  if (mode === "single_user" || me) redirect("/");

  const hasAnyUser = mode === "multi_user";

  return (
    <main className="flex min-h-screen items-center justify-center bg-carbon px-4">
      <div className="w-full max-w-sm rounded-2xl bg-warm-fog/5 p-6 shadow-xl ring-1 ring-aether-teal/20">
        <h1 className="mb-4 text-xl font-semibold text-aether-teal">
          {hasAnyUser ? "Sign in to LangPerf" : "Set up LangPerf"}
        </h1>
        <LoginForm bootstrap={!hasAnyUser} />
      </div>
    </main>
  );
}
