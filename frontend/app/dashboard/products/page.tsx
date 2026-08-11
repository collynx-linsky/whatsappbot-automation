"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { DashboardShell } from "@/components/DashboardShell";
import { Field } from "@/components/Field";
import {
  ApiError,
  createOrder,
  createProduct,
  listCustomers,
  listOrders,
  listProducts,
  updateOrderStatus,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/useAuth";
import type { Customer, Order, OrderStatus, Product } from "@/types";

// Mirrors backend apps.orders.models.Order.ALLOWED_TRANSITIONS exactly —
// keep these in sync if the state machine changes server-side.
const ALLOWED_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  pending: ["confirmed", "cancelled"],
  confirmed: ["processing", "cancelled"],
  processing: ["ready", "cancelled"],
  ready: ["delivered", "cancelled"],
  delivered: [],
  cancelled: [],
};

const STATUS_LABEL: Record<OrderStatus, string> = {
  pending: "Pending",
  confirmed: "Confirmed",
  processing: "Processing",
  ready: "Ready",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

const emptyProductForm = { name: "", sku: "", category: "", price: "", stock: "0" };
const emptyOrderForm = { customer: "", product: "", quantity: "1" };

export default function ProductsPage() {
  const { user, ready } = useRequireAuth();
  const [products, setProducts] = useState<Product[] | null>(null);
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [customers, setCustomers] = useState<Customer[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [productForm, setProductForm] = useState(emptyProductForm);
  const [orderForm, setOrderForm] = useState(emptyOrderForm);
  const [submittingProduct, setSubmittingProduct] = useState(false);
  const [submittingOrder, setSubmittingOrder] = useState(false);

  async function refreshAll() {
    try {
      const [productsRes, ordersRes, customersRes] = await Promise.all([
        listProducts(),
        listOrders(),
        listCustomers(),
      ]);
      setProducts(productsRes.results);
      setOrders(ordersRes.results);
      setCustomers(customersRes.results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load catalog.");
    }
  }

  useEffect(() => {
    if (!ready) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshAll();
  }, [ready]);

  async function handleAddProduct(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmittingProduct(true);
    try {
      await createProduct({
        name: productForm.name,
        sku: productForm.sku || undefined,
        category: productForm.category || undefined,
        price: productForm.price,
        stock: Number(productForm.stock) || 0,
      });
      setSuccess(`Added ${productForm.name} to the catalog.`);
      setProductForm(emptyProductForm);
      await refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add product.");
    } finally {
      setSubmittingProduct(false);
    }
  }

  async function handleCreateOrder(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmittingOrder(true);
    try {
      await createOrder({
        customer: orderForm.customer,
        items: [{ product: orderForm.product, quantity: Number(orderForm.quantity) || 1 }],
      });
      setSuccess("Order created (pending confirmation).");
      setOrderForm(emptyOrderForm);
      await refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create order.");
    } finally {
      setSubmittingOrder(false);
    }
  }

  async function handleTransition(order: Order, next: OrderStatus) {
    setError(null);
    try {
      await updateOrderStatus(order.id, next);
      await refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update order status.");
    }
  }

  if (!ready || !user) {
    return <div className="flex flex-1 items-center justify-center text-zinc-500">Loading…</div>;
  }

  const canManageCatalog = user.role === "business_owner" || user.role === "manager";

  return (
    <DashboardShell
      user={user}
      title="Products & Orders"
      nav={[
        { label: "Overview", href: "/dashboard" },
        { label: "Products & Orders", href: "/dashboard/products" },
        { label: "Inbox", href: "/dashboard/inbox" },
        { label: "AI Assistant", href: "/dashboard/ai" },
        { label: "Knowledge Base", href: "/dashboard/knowledge" },
        { label: "Campaigns", href: "/dashboard/campaigns" },
        { label: "WhatsApp", href: "/dashboard/whatsapp" },
        { label: "Billing", href: "/dashboard/billing" },
        { label: "Analytics", href: "/dashboard/analytics" },
      ]}
    >
      <div className="space-y-8">
        {error && <Alert kind="error" message={error} />}
        {success && <Alert kind="success" message={success} />}

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Catalog
          </h2>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">SKU</th>
                  <th className="px-4 py-2 font-medium">Price</th>
                  <th className="px-4 py-2 font-medium">Stock</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {products?.map((p) => (
                  <tr key={p.id} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                    <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{p.name}</td>
                    <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">{p.sku || "—"}</td>
                    <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">
                      {p.currency} {p.price}
                    </td>
                    <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">{p.stock}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          p.is_orderable
                            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300"
                            : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                        }`}
                      >
                        {p.is_orderable ? "Orderable" : p.status}
                      </span>
                    </td>
                  </tr>
                ))}
                {products?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-zinc-500">
                      No products yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {canManageCatalog && (
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Add a Product
            </h2>
            <form
              onSubmit={handleAddProduct}
              className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <Field
                label="Name"
                value={productForm.name}
                onChange={(v) => setProductForm({ ...productForm, name: v })}
                required
              />
              <Field
                label="SKU (optional)"
                value={productForm.sku}
                onChange={(v) => setProductForm({ ...productForm, sku: v })}
              />
              <Field
                label="Category"
                value={productForm.category}
                onChange={(v) => setProductForm({ ...productForm, category: v })}
              />
              <Field
                label="Price"
                type="number"
                value={productForm.price}
                onChange={(v) => setProductForm({ ...productForm, price: v })}
                required
              />
              <Field
                label="Stock"
                type="number"
                value={productForm.stock}
                onChange={(v) => setProductForm({ ...productForm, stock: v })}
              />
              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={submittingProduct}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submittingProduct ? "Adding…" : "Add Product"}
                </button>
              </div>
            </form>
          </section>
        )}

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Orders
          </h2>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Customer</th>
                  <th className="px-4 py-2 font-medium">Items</th>
                  <th className="px-4 py-2 font-medium">Total</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {orders?.map((o) => (
                  <tr key={o.id} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                    <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{o.customer_name}</td>
                    <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">
                      {o.items.map((i) => `${i.quantity}× ${i.product_name}`).join(", ")}
                    </td>
                    <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">
                      {o.currency} {o.total_amount}
                    </td>
                    <td className="px-4 py-2">
                      <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                        {STATUS_LABEL[o.status]}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex gap-2">
                        {ALLOWED_TRANSITIONS[o.status].map((next) => (
                          <button
                            key={next}
                            onClick={() => handleTransition(o, next)}
                            className="text-sm font-medium text-emerald-600 hover:underline dark:text-emerald-400"
                          >
                            {STATUS_LABEL[next]}
                          </button>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
                {orders?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-zinc-500">
                      No orders yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Create an Order
          </h2>
          <form
            onSubmit={handleCreateOrder}
            className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-3 dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Customer
              </label>
              <select
                required
                value={orderForm.customer}
                onChange={(e) => setOrderForm({ ...orderForm, customer: e.target.value })}
                className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
              >
                <option value="">Select a customer…</option>
                {customers?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name || c.phone}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Product
              </label>
              <select
                required
                value={orderForm.product}
                onChange={(e) => setOrderForm({ ...orderForm, product: e.target.value })}
                className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
              >
                <option value="">Select a product…</option>
                {products?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.currency} {p.price})
                  </option>
                ))}
              </select>
            </div>
            <Field
              label="Quantity"
              type="number"
              value={orderForm.quantity}
              onChange={(v) => setOrderForm({ ...orderForm, quantity: v })}
              required
            />
            <div className="sm:col-span-3">
              <button
                type="submit"
                disabled={submittingOrder}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submittingOrder ? "Creating…" : "Create Order"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </DashboardShell>
  );
}
