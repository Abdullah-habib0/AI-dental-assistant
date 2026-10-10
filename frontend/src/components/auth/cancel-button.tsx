"use client";

import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { cancelAppointment } from "@/lib/actions";

/** Cancel, in two clicks: the first asks, the second does it. */
export function CancelButton({ appointmentId }: { appointmentId: number }) {
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function confirm() {
    startTransition(async () => {
      const result = await cancelAppointment(appointmentId);
      // On success the page refreshes and this appointment disappears from the list.
      setError(result.error);
      setAsking(false);
    });
  }

  return (
    <div className="flex flex-col items-end gap-2">
      {asking ? (
        <div className="flex gap-2">
          <Button variant="ghost" size="lg" onClick={() => setAsking(false)} disabled={pending}>
            Keep it
          </Button>
          <Button variant="destructive" size="lg" disabled={pending} onClick={confirm}>
            {pending ? "Cancelling…" : "Yes, cancel it"}
          </Button>
        </div>
      ) : (
        <Button
          variant="ghost"
          size="lg"
          className="text-destructive hover:bg-destructive/10 hover:text-destructive"
          onClick={() => {
            setError(null);
            setAsking(true);
          }}
        >
          Cancel
        </Button>
      )}
      {/* Outside both states, so a failure is still shown after the buttons reset. */}
      {error && (
        <p role="alert" className="max-w-56 text-right text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
