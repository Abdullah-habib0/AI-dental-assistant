import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthCard } from "@/components/auth/auth-card";
import { RegisterForm } from "@/components/auth/auth-forms";

export const metadata: Metadata = { title: "Create an account" };

export default function RegisterPage() {
  return (
    <AuthCard title="Create an account" intro="See all your appointments in one place, and book without retyping your details.">
      <Suspense>
        <RegisterForm />
      </Suspense>
    </AuthCard>
  );
}
