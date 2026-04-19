import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { fetchMode, fetchMe } from "@/lib/auth";
import { LoginForm } from "@/components/auth/login-form";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  const cookie = headers().get("cookie") ?? undefined;
  const [mode, me] = await Promise.all([fetchMode(), fetchMe(cookie)]);
  if (me) redirect("/");

  const bootstrap = mode === "single_user";

  return (
    <main className="flex min-h-screen items-center justify-center bg-carbon px-4">
      <div className="w-full max-w-sm rounded-2xl bg-warm-fog/5 p-6 shadow-xl ring-1 ring-aether-teal/20">
        <h1 className="mb-1 text-xl font-semibold text-aether-teal">
          {bootstrap ? "Set up LangPerf" : "Sign in to LangPerf"}
        </h1>
        {bootstrap && (
          <p className="mb-4 text-xs text-steel-mist">
            Create the first admin account for this deployment.
          </p>
        )}
        <LoginForm bootstrap={bootstrap} />
      </div>
    </main>
  );
}
