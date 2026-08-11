"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { FinalCTA } from "@/components/marketing/FinalCTA";
import { Hero } from "@/components/marketing/Hero";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";
import { MarketingNav } from "@/components/marketing/MarketingNav";
import { Pricing } from "@/components/marketing/Pricing";
import { SecuritySection } from "@/components/marketing/SecuritySection";
import { dashboardPathForRole, getStoredUser } from "@/lib/auth";

// The public marketing/landing page. An already-signed-in visitor is
// bounced straight to their dashboard (checked client-side, since JWTs
// live in localStorage — see lib/auth.ts's own note on why this app has
// no server-side session to check); everyone else sees the real page,
// not a loading spinner, since most visitors here have never signed in.
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const user = getStoredUser();
    if (user) router.replace(dashboardPathForRole(user.role));
  }, [router]);

  return (
    <div className="flex flex-1 flex-col">
      <MarketingNav />
      <main>
        <Hero />
        <FeatureGrid />
        <HowItWorks />
        <SecuritySection />
        <Pricing />
        <FinalCTA />
      </main>
      <MarketingFooter />
    </div>
  );
}
