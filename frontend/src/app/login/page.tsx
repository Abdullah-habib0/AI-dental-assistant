import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthCard } from "@/components/auth/auth-card";
import { LoginForm } from "@/components/auth/auth-forms";

export const metadata: Metadata = { title: "Log in" };

export default function LoginPage() {
  return (
    <AuthCard title="Welcome back" intro="Log in to see and manage your appointments.">
      {/* The form reads ?next= from the address, which is only known once someone visits. */}
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthCard>
  );
}
