"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Alert } from "@/components/Alert";
import { DashboardShell } from "@/components/DashboardShell";
import { PageLoading } from "@/components/PageLoading";
import { DASHBOARD_NAV } from "@/lib/navigation";
import {
  assignConversation,
  createConversation,
  listConversations,
  listCustomers,
  listMessages,
  listStaff,
  sendMessage,
  updateConversation,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useRequireAuth } from "@/lib/useAuth";
import type { Conversation, ConversationStatus, Customer, Message, StaffMember } from "@/types";

const STATUS_LABEL: Record<ConversationStatus, string> = {
  open: "Open",
  pending: "Pending",
  resolved: "Resolved",
  closed: "Closed",
};

const STATUS_BADGE: Record<ConversationStatus, string> = {
  open: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
  pending: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  resolved: "bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300",
  closed: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

// No real-time channel exists on the backend (no websockets/SSE) — this
// page polls instead. The conversation list polls slowly (new conversations
// / unread counts don't need to be instant); the open thread polls faster
// so replies feel reasonably live.
const CONVERSATION_POLL_MS = 15000;
const MESSAGE_POLL_MS = 4000;

export default function InboxPage() {
  const { user, ready } = useRequireAuth();
  const [conversations, setConversations] = useState<Conversation[] | null>(null);
  const [statusFilter, setStatusFilter] = useState<ConversationStatus | "">("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [staff, setStaff] = useState<StaffMember[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [composerText, setComposerText] = useState("");
  const [sending, setSending] = useState(false);

  const [showNewForm, setShowNewForm] = useState(false);
  const [customerSearch, setCustomerSearch] = useState("");
  const [customerResults, setCustomerResults] = useState<Customer[] | null>(null);
  const [newCustomerId, setNewCustomerId] = useState("");
  const [creating, setCreating] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const selected = useMemo(
    () => conversations?.find((c) => c.id === selectedId) ?? null,
    [conversations, selectedId],
  );

  async function refreshConversations() {
    try {
      const res = await listConversations({
        status: statusFilter || undefined,
        ordering: "-last_message_at",
      });
      setConversations(res.results);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load conversations."));
    }
  }

  async function refreshMessages(conversationId: string) {
    try {
      const res = await listMessages(conversationId);
      setMessages(res.results);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load messages."));
    }
  }

  useEffect(() => {
    if (!ready) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshConversations();
    listStaff()
      .then((res) => setStaff(res.results))
      .catch(() => {
        /* staff list is only needed for the assignee dropdown — a failure
           here shouldn't block the rest of the inbox from working */
      });
    const interval = setInterval(refreshConversations, CONVERSATION_POLL_MS);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, statusFilter]);

  useEffect(() => {
    if (!selectedId) {
      // Switching away from a conversation — clear the stale thread rather
      // than let it flash the previous conversation's messages.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMessages(null);
      return;
    }
    refreshMessages(selectedId);
    const interval = setInterval(() => refreshMessages(selectedId), MESSAGE_POLL_MS);
    return () => clearInterval(interval);
  }, [selectedId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedId || !composerText.trim()) return;
    setError(null);
    setSending(true);
    try {
      await sendMessage(selectedId, composerText.trim());
      setComposerText("");
      await refreshMessages(selectedId);
      await refreshConversations();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to send message."));
    } finally {
      setSending(false);
    }
  }

  async function handleStatusChange(next: ConversationStatus) {
    if (!selected) return;
    setError(null);
    try {
      await updateConversation(selected.id, { status: next });
      await refreshConversations();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to update status."));
    }
  }

  async function handleAssign(userId: string) {
    if (!selected) return;
    setError(null);
    try {
      await assignConversation(selected.id, userId || null);
      await refreshConversations();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to reassign conversation."));
    }
  }

  async function handleToggleAi() {
    if (!selected) return;
    setError(null);
    try {
      await updateConversation(selected.id, { ai_enabled: !selected.ai_enabled });
      await refreshConversations();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to update AI handoff."));
    }
  }

  async function handleCustomerSearch(e: React.FormEvent) {
    e.preventDefault();
    try {
      const res = await listCustomers({ search: customerSearch || undefined });
      setCustomerResults(res.results);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to search customers."));
    }
  }

  async function handleCreateConversation(e: React.FormEvent) {
    e.preventDefault();
    if (!newCustomerId) return;
    setError(null);
    setCreating(true);
    try {
      const conversation = await createConversation({ customer: newCustomerId });
      setShowNewForm(false);
      setCustomerSearch("");
      setCustomerResults(null);
      setNewCustomerId("");
      await refreshConversations();
      setSelectedId(conversation.id);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to start conversation."));
    } finally {
      setCreating(false);
    }
  }

  if (!ready || !user) {
    return <PageLoading />;
  }

  return (
    <DashboardShell
      user={user}
      title="Inbox"
      nav={DASHBOARD_NAV}
    >
      <div className="space-y-4">
        {error && <Alert kind="error" message={error} />}

        <div className="flex h-[70vh] gap-4 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          {/* ── Left pane: conversation list ─────────────────── */}
          {/* Below lg, this two-pane layout can't fit both at once (a
              fixed w-80 list pane left ~70px for the thread on a 390px
              phone, clipped instead of readable) — so on mobile, show
              exactly one pane at a time: the list until a conversation is
              selected, then the thread (with a Back control) instead. */}
          <div
            className={`w-full shrink-0 flex-col border-r border-zinc-200 lg:flex lg:w-80 dark:border-zinc-800 ${selected ? "hidden lg:flex" : "flex"}`}
          >
            <div className="flex items-center justify-between gap-2 border-b border-zinc-200 p-3 dark:border-zinc-800">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as ConversationStatus | "")}
                className="rounded-lg border border-zinc-300 bg-white px-2 py-1 text-xs text-zinc-700 outline-none focus:border-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200"
              >
                <option value="">All statuses</option>
                {(Object.keys(STATUS_LABEL) as ConversationStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
              <button
                onClick={() => setShowNewForm((v) => !v)}
                className="rounded-lg bg-emerald-600 px-2 py-1 text-xs font-medium text-white hover:bg-emerald-700"
              >
                + New
              </button>
            </div>

            {showNewForm && (
              <div className="space-y-2 border-b border-zinc-200 p-3 dark:border-zinc-800">
                <form onSubmit={handleCustomerSearch} className="flex gap-1">
                  <input
                    value={customerSearch}
                    onChange={(e) => setCustomerSearch(e.target.value)}
                    placeholder="Search customers…"
                    className="w-full rounded-lg border border-zinc-300 bg-white px-2 py-1 text-xs text-zinc-900 outline-none focus:border-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                  />
                  <button
                    type="submit"
                    className="rounded-lg border border-zinc-300 px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
                  >
                    Search
                  </button>
                </form>
                <form onSubmit={handleCreateConversation} className="flex gap-1">
                  <select
                    value={newCustomerId}
                    onChange={(e) => setNewCustomerId(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-2 py-1 text-xs text-zinc-900 outline-none focus:border-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                  >
                    <option value="">Select a customer…</option>
                    {(customerResults ?? []).map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name || c.phone}
                      </option>
                    ))}
                  </select>
                  <button
                    type="submit"
                    disabled={!newCustomerId || creating}
                    className="rounded-lg bg-emerald-600 px-2 py-1 text-xs font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {creating ? "…" : "Start"}
                  </button>
                </form>
              </div>
            )}

            <div className="flex-1 overflow-y-auto">
              {conversations === null && !error && (
                <p className="p-4 text-center text-sm text-zinc-500">Loading…</p>
              )}
              {conversations?.length === 0 && (
                <p className="p-4 text-center text-sm text-zinc-500">No conversations yet.</p>
              )}
              {conversations?.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  className={`block w-full border-b border-zinc-100 p-3 text-left transition-colors dark:border-zinc-800 ${
                    c.id === selectedId
                      ? "bg-emerald-50 dark:bg-emerald-950/30"
                      : "hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {c.customer_name || c.customer_phone}
                    </span>
                    {c.unread_count > 0 && (
                      <span className="rounded-full bg-emerald-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                        {c.unread_count}
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-xs text-zinc-500 dark:text-zinc-400">
                    {c.last_message_preview || "No messages yet"}
                  </p>
                  <div className="mt-1 flex items-center gap-2">
                    <span
                      className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${STATUS_BADGE[c.status]}`}
                    >
                      {STATUS_LABEL[c.status]}
                    </span>
                    <span className="text-[10px] text-zinc-400">
                      {c.assigned_to_name ?? "Unassigned"}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* ── Right pane: thread ───────────────────────────── */}
          <div className={`flex-1 flex-col ${selected ? "flex" : "hidden lg:flex"}`}>
            {!selected && (
              <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">
                Select a conversation to view it.
              </div>
            )}

            {selected && (
              <>
                <div className="flex flex-wrap items-center gap-3 border-b border-zinc-200 p-3 dark:border-zinc-800">
                  <button
                    onClick={() => setSelectedId(null)}
                    aria-label="Back to conversations"
                    className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-100 lg:hidden dark:text-zinc-400 dark:hover:bg-zinc-800"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-4 w-4">
                      <path d="M15 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                  <div>
                    <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                      {selected.customer_name || selected.customer_phone}
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      {selected.customer_phone}
                    </p>
                  </div>
                  <select
                    value={selected.status}
                    onChange={(e) => handleStatusChange(e.target.value as ConversationStatus)}
                    className="rounded-lg border border-zinc-300 bg-white px-2 py-1 text-xs text-zinc-700 outline-none focus:border-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200"
                  >
                    {(Object.keys(STATUS_LABEL) as ConversationStatus[]).map((s) => (
                      <option key={s} value={s}>
                        {STATUS_LABEL[s]}
                      </option>
                    ))}
                  </select>
                  <select
                    value={selected.assigned_to ?? ""}
                    onChange={(e) => handleAssign(e.target.value)}
                    className="rounded-lg border border-zinc-300 bg-white px-2 py-1 text-xs text-zinc-700 outline-none focus:border-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200"
                  >
                    <option value="">Unassigned</option>
                    {staff?.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.full_name}
                      </option>
                    ))}
                  </select>
                  <label className="flex items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-300">
                    <input
                      type="checkbox"
                      checked={selected.ai_enabled}
                      onChange={handleToggleAi}
                    />
                    AI handling
                  </label>
                </div>

                <div className="flex-1 space-y-2 overflow-y-auto p-4">
                  {messages === null && <p className="text-center text-sm text-zinc-500">Loading…</p>}
                  {messages?.length === 0 && (
                    <p className="text-center text-sm text-zinc-500">No messages yet.</p>
                  )}
                  {messages?.map((m) => {
                    if (m.sender_type === "system") {
                      return (
                        <p key={m.id} className="text-center text-xs text-zinc-400">
                          {m.content}
                        </p>
                      );
                    }
                    const isOutbound = m.sender_type === "staff" || m.sender_type === "ai";
                    return (
                      <div key={m.id} className={`flex ${isOutbound ? "justify-end" : "justify-start"}`}>
                        <div
                          className={`max-w-[70%] rounded-xl px-3 py-2 text-sm ${
                            isOutbound
                              ? "bg-emerald-600 text-white"
                              : "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                          }`}
                        >
                          <p className="whitespace-pre-wrap">{m.content}</p>
                          <p
                            className={`mt-1 text-[10px] ${
                              isOutbound ? "text-emerald-100" : "text-zinc-400"
                            }`}
                          >
                            {m.sender_type === "ai" ? "AI" : m.sender_name ?? m.sender_type} ·{" "}
                            {new Date(m.created_at).toLocaleTimeString()}
                            {isOutbound && m.status === "failed" ? " · failed to send" : ""}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={messagesEndRef} />
                </div>

                <form
                  onSubmit={handleSend}
                  className="flex gap-2 border-t border-zinc-200 p-3 dark:border-zinc-800"
                >
                  <textarea
                    value={composerText}
                    onChange={(e) => setComposerText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSend(e);
                      }
                    }}
                    rows={1}
                    placeholder="Type a reply…"
                    className="flex-1 resize-none rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                  />
                  <button
                    type="submit"
                    disabled={sending || !composerText.trim()}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {sending ? "Sending…" : "Send"}
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
