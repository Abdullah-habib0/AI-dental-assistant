import type { Metadata } from "next";
import { Fraunces, Geist } from "next/font/google";
import { Suspense } from "react";

import { ChatProvider } from "@/components/chat/chat-context";
import { ChatWidget } from "@/components/chat/chat-widget";
import { AccountLink, AccountLinkPlaceholder } from "@/components/site/account-link";
import { SiteFooter, SiteFooterSkeleton } from "@/components/site/site-footer";
import { SiteHeader } from "@/components/site/site-header";
import { site } from "@/lib/site";
import "./globals.css";

const body = Geist({ variable: "--font-body", subsets: ["latin"] });
const display = Fraunces({ variable: "--font-display", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: `${site.name} - ${site.tagline}`, template: `%s · ${site.name}` },
  description:
    "Check-ups, fillings, whitening, root canal treatment and implants on the High Street - with an assistant that answers questions and books appointments any time.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${body.variable} ${display.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <ChatProvider>
          <SiteHeader
            account={
              <Suspense fallback={<AccountLinkPlaceholder />}>
                <AccountLink />
              </Suspense>
            }
            mobileAccount={
              <Suspense fallback={<AccountLinkPlaceholder />}>
                <AccountLink />
              </Suspense>
            }
          />
          <main className="flex-1">{children}</main>
          <Suspense fallback={<SiteFooterSkeleton />}>
            <SiteFooter />
          </Suspense>
          <ChatWidget />
        </ChatProvider>
      </body>
    </html>
  );
}
