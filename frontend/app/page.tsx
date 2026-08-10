"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { dashboardPathForRole, getStoredUser } from "@/lib/auth";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const user = getStoredUser();
    router.replace(user ? dashboardPathForRole(user.role) : "/login");
  }, [router]);

  return <div className="flex flex-1 items-center justify-center text-zinc-500">Loading…</div>;
}
