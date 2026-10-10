import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { CalendarDays, Clock, UserRound } from "lucide-react";

import { CancelButton } from "@/components/auth/cancel-button";
import { OpenChatButton } from "@/components/chat/chat-context";
import { PageHeader } from "@/components/site/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { logout } from "@/lib/actions";
import { getClinicInfo } from "@/lib/api";
import { backendFetch } from "@/lib/backend";
import { getAccessToken, type User } from "@/lib/session";

export const metadata: Metadata = { title: "My appointments" };

type Appointment = {
  id: number;
  service_name: string;
  dentist_name: string;
  start_time: string; // UTC, e.g. "2026-10-14T09:00:00Z"
  end_time: string;
};

export default function AccountPage() {
  return (
    <>
      <PageHeader eyebrow="Your account" title="My appointments" />
      <div className="mx-auto mt-10 max-w-3xl px-4 sm:px-6">
        {/* Reading the login cookie only happens once someone visits, so this streams in. */}
        <Suspense fallback={<AccountSkeleton />}>
          <Account />
        </Suspense>
      </div>
    </>
  );
}

async function Account() {
  const token = await getAccessToken();
  if (!token) redirect("/login?next=/account");

  const [meResponse, appointmentsResponse, clinic] = await Promise.all([
    backendFetch("/auth/me", { token }),
    // The backend finds the appointments from the login itself - no phone number needed.
    backendFetch("/appointments/mine", { method: "POST", body: {}, token }),
    getClinicInfo(),
  ]);
  if (!meResponse.ok) redirect("/login?next=/account");
  const user = (await meResponse.json()) as User;
  const appointments = appointmentsResponse.ok ? ((await appointmentsResponse.json()) as Appointment[]) : [];

  // Shown in clinic time, whatever the visitor's own computer is set to.
  const day = new Intl.DateTimeFormat("en-GB", { timeZone: clinic.timezone, weekday: "long", day: "numeric", month: "long" });
  const time = new Intl.DateTimeFormat("en-GB", { timeZone: clinic.timezone, hour: "2-digit", minute: "2-digit" });

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="text-lg">
          Hello, <span className="font-medium">{user.full_name}</span>
          <span className="block text-sm text-muted-foreground">{user.email}</span>
        </p>
        <form action={logout}>
          <Button type="submit" variant="outline" size="lg">
            Log out
          </Button>
        </form>
      </div>

      {appointments.length === 0 ? (
        <div className="rounded-2xl border border-dashed bg-card p-10 text-center">
          <CalendarDays className="mx-auto size-8 text-primary" />
          <p className="mt-4 font-heading text-xl font-semibold">No upcoming appointments</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Book through the assistant while you&apos;re logged in, and it&apos;ll appear here.
          </p>
          <OpenChatButton className="mt-6" message="I'd like to book an appointment">
            Book an appointment
          </OpenChatButton>
        </div>
      ) : (
        <ul className="space-y-4">
          {appointments.map((a) => {
            const start = new Date(a.start_time);
            const when = `${day.format(start)} at ${time.format(start)}`;
            return (
              <li key={a.id} className="rounded-2xl border bg-card p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-semibold">{a.service_name}</h2>
                    <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
                      <Clock className="size-4" /> {when} to {time.format(new Date(a.end_time))}
                    </p>
                    <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
                      <UserRound className="size-4" /> {a.dentist_name}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-start gap-2">
                    <OpenChatButton
                      variant="outline"
                      size="lg"
                      showIcon={false}
                      message={`I'd like to move my ${a.service_name.toLowerCase()} appointment on ${when} (appointment #${a.id})`}
                    >
                      Move
                    </OpenChatButton>
                    <CancelButton appointmentId={a.id} />
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <p className="text-sm text-muted-foreground">
        Free to cancel or move with at least 24 hours&apos; notice. Appointments booked as a guest, before you had an
        account, don&apos;t appear here - ask the assistant about those with the phone number you used.
      </p>
    </div>
  );
}

function AccountSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-32 w-full rounded-2xl" />
      <Skeleton className="h-32 w-full rounded-2xl" />
    </div>
  );
}
