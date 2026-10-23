"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { Category, Expense, ExpenseSummary } from "@/lib/types";
import { formatCurrency, formatDateTime } from "@/lib/formatters";
import { expenseApi } from "@/lib/api";

type IconName = "grid" | "receipt" | "tag" | "plus" | "search" | "arrow" | "close" | "wallet" | "chart";

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, React.ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
    receipt: <><path d="M5 3h14v18l-3-2-4 2-4-2-3 2z" /><path d="M8 8h8M8 12h8M8 16h4" /></>,
    tag: <><path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8Z" /><circle cx="8" cy="8" r="1" /></>,
    plus: <><path d="M12 5v14M5 12h14" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    arrow: <><path d="M7 17 17 7M7 7h10v10" /></>,
    close: <><path d="m18 6-12 12M6 6l12 12" /></>,
    wallet: <><path d="M4 6.5A2.5 2.5 0 0 1 6.5 4H20v16H6a2 2 0 0 1-2-2z" /><path d="M4 7h16M16 13h4" /><circle cx="16" cy="13" r=".5" /></>,
    chart: <><path d="M4 19V5M4 19h17" /><path d="m7 15 4-4 3 2 6-7" /></>,
  };

  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      {paths[name]}
    </svg>
  );
}

const categoryColors = ["sage", "blue", "amber", "rose", "violet", "teal"];

function getCategoryColor(categoryName: string, categories: Category[]) {
  const categoryIndex = categories.findIndex((category) => category.name === categoryName);
  return categoryColors[Math.max(categoryIndex, 0) % categoryColors.length];
}

export default function Home() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [summary, setSummary] = useState<ExpenseSummary>({ total: 0, count: 0, average: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [dashboardError, setDashboardError] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [categoryMessage, setCategoryMessage] = useState("");
  const [categoryError, setCategoryError] = useState("");
  const [isAddingCategory, setIsAddingCategory] = useState(false);
  const [expenseTitle, setExpenseTitle] = useState("");
  const [expenseAmount, setExpenseAmount] = useState("");
  const [expenseCategory, setExpenseCategory] = useState("");
  const [expenseError, setExpenseError] = useState("");
  const [expenseMessage, setExpenseMessage] = useState("");
  const [isExpenseOpen, setIsExpenseOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [query, setQuery] = useState("");
  const [activeSection, setActiveSection] = useState("overview");

  const filteredExpenses = useMemo(
    () =>
      expenses.filter((expense) =>
        `${expense.title} ${expense.category}`.toLowerCase().includes(query.trim().toLowerCase()),
      ),
    [expenses, query],
  );

  const fetchDashboard = useCallback(
    () =>
      Promise.all([
        expenseApi.getCategories(),
        expenseApi.getExpenses(),
        expenseApi.getSummary(),
      ]),
    [],
  );

  const refreshDashboard = useCallback(async () => {
    setIsLoading(true);
    setDashboardError("");
    try {
      const [nextCategories, nextExpenses, nextSummary] = await fetchDashboard();
      setCategories(nextCategories);
      setExpenses(nextExpenses);
      setSummary(nextSummary);
      setHasLoaded(true);
    } finally {
      setIsLoading(false);
    }
  }, [fetchDashboard]);

  useEffect(() => {
    let isMounted = true;
    void fetchDashboard()
      .then(([nextCategories, nextExpenses, nextSummary]) => {
        if (!isMounted) return;
        setCategories(nextCategories);
        setExpenses(nextExpenses);
        setSummary(nextSummary);
        setHasLoaded(true);
      })
      .catch((error: unknown) => {
        if (!isMounted) return;
        setDashboardError(
          error instanceof Error ? error.message : "Could not load saved data from the backend.",
        );
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [fetchDashboard]);

  async function addCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = categoryName.trim();
    setCategoryMessage("");
    setCategoryError("");
    if (!name) {
      setCategoryError("Enter a category name to continue.");
      return;
    }
    if (categories.some((category) => category.name.toLowerCase() === name.toLowerCase())) {
      setCategoryError("That category already exists.");
      return;
    }
    setIsAddingCategory(true);
    try {
      await expenseApi.createCategory({ name });
      setCategoryName("");
      setCategoryMessage(`${name} saved to your database.`);
      try {
        await refreshDashboard();
      } catch {
        setCategoryError(`${name} was saved, but the dashboard could not refresh. Try refreshing the page.`);
      }
    } catch (error) {
      setCategoryError(
        error instanceof Error ? error.message : "We couldn't save that category. Please try again.",
      );
    } finally {
      setIsAddingCategory(false);
    }
  }

  async function addExpense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setExpenseError("");
    setExpenseMessage("");
    const title = expenseTitle.trim();
    const amount = Number(expenseAmount);
    const category = categories.find((item) => item.id === Number(expenseCategory));

    if (!title) {
      setExpenseError("Add a title for this expense.");
      return;
    }
    if (!expenseAmount || !Number.isFinite(amount) || amount <= 0) {
      setExpenseError("Enter an amount greater than ₹0.");
      return;
    }
    if (!category) {
      setExpenseError("Choose a category before adding this expense.");
      return;
    }

    setIsSubmitting(true);
    try {
      const createdExpense = await expenseApi.createExpense({
        title,
        amount,
        category_id: category.id,
      });
      const newExpense: Expense = {
        ...createdExpense,
        category: category.name,
      };
      setExpenses((current) => [newExpense, ...current]);
      setSummary((current) => {
        const total = current.total + createdExpense.amount;
        const count = current.count + 1;
        return { total, count, average: total / count };
      });
      setCategories((current) =>
        current.map((item) =>
          item.id === category.id ? { ...item, total_expenses: item.total_expenses + 1 } : item,
        ),
      );
      setExpenseTitle("");
      setExpenseAmount("");
      setExpenseCategory("");
      setIsExpenseOpen(false);
      setExpenseMessage("Expense saved to your database.");
      try {
        await refreshDashboard();
      } catch {
        setExpenseMessage("Expense saved. The dashboard could not refresh; reload the page to sync.");
      }
    } catch (error) {
      setExpenseError(
        error instanceof Error ? error.message : "We couldn't save that expense. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  function navigate(section: string) {
    setActiveSection(section);
    document.getElementById(section)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview" onClick={() => setActiveSection("overview")} aria-label="Ledger home">
          <span className="brand-mark"><Icon name="chart" size={21} /></span>
          <span className="brand-name">ledger<span>.</span></span>
        </a>
        <div className="side-caption">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <button className={`nav-link ${activeSection === "overview" ? "active" : ""}`} onClick={() => navigate("overview")}><Icon name="grid" />Overview</button>
          <button className={`nav-link ${activeSection === "expenses" ? "active" : ""}`} onClick={() => navigate("expenses")}><Icon name="receipt" />Expenses<span className="nav-count">{expenses.length}</span></button>
          <button className={`nav-link ${activeSection === "categories" ? "active" : ""}`} onClick={() => navigate("categories")}><Icon name="tag" />Categories</button>
        </nav>
        <div className="sidebar-bottom">
          <div className="demo-note"><span className="demo-dot" /><span><strong>{hasLoaded ? "SQLite connected" : isLoading ? "Connecting…" : "Backend unavailable"}</strong><small>{hasLoaded ? "Your data is saved" : isLoading ? "Loading saved data" : "Check the backend server"}</small></span></div>
          <div className="profile"><div className="avatar">A</div><span className="profile-copy"><strong>Your account</strong><small>Personal space</small></span><span className="profile-more">···</span></div>
        </div>
      </aside>

      <main className="main-content" id="overview">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>Overview</strong></div>
          <div className="topbar-right"><span className="today-label">{new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", month: "short" }).format(new Date())}</span><span className="top-avatar" aria-label="Your account">A</span></div>
        </header>

        <div className="page-wrap">
          <section className="page-heading">
            <div>
              <div className="eyebrow"><span className="live-dot" />YOUR MONEY, IN FOCUS</div>
              <h1>Overview</h1>
              <p className="page-description">A little clarity goes a long way. Here&apos;s where things stand.</p>
            </div>
            <button className="button button-primary" disabled={!hasLoaded || Boolean(dashboardError)} onClick={() => { setIsExpenseOpen(true); setExpenseError(""); }}>
              <Icon name="plus" size={17} /> Add expense
            </button>
          </section>

          {expenseMessage && <div className="toast-message" role="status"><span className="status-check">✓</span>{expenseMessage}<button onClick={() => setExpenseMessage("")} aria-label="Dismiss message"><Icon name="close" size={15} /></button></div>}
          {dashboardError && <div className="dashboard-error" role="alert"><span>{dashboardError}</span><button className="button button-secondary" onClick={() => { void refreshDashboard().catch((error: unknown) => setDashboardError(error instanceof Error ? error.message : "Could not load saved data.")); }}>Retry connection</button></div>}

          <section className="summary-grid" aria-label="Spending summary">
            <article className="summary-card total-card">
              <div className="summary-top"><span className="summary-label">Total spending</span><span className="summary-icon green-icon"><Icon name="wallet" size={18} /></span></div>
              <div className="summary-value">{formatCurrency(summary.total)}</div>
              <div className="summary-foot"><span className="foot-mark">↗</span> Across all your expenses</div>
            </article>
            <article className="summary-card">
              <div className="summary-top"><span className="summary-label">Total expenses</span><span className="summary-icon gray-icon"><Icon name="receipt" size={18} /></span></div>
              <div className="summary-value">{summary.count}<span className="value-unit"> {summary.count === 1 ? "expense" : "expenses"}</span></div>
              <div className="summary-foot">Recorded in this workspace</div>
            </article>
            <article className="summary-card">
              <div className="summary-top"><span className="summary-label">Average expense</span><span className="summary-icon amber-icon"><Icon name="chart" size={18} /></span></div>
              <div className="summary-value">{formatCurrency(summary.average)}</div>
              <div className="summary-foot">Per recorded expense</div>
            </article>
          </section>

          <section className="content-grid">
            <div className="panel activity-panel" id="expenses">
              <div className="panel-heading">
                <div><div className="section-kicker">YOUR ACTIVITY</div><h2>Recent expenses</h2></div>
                <span className="table-count">{expenses.length} {expenses.length === 1 ? "entry" : "entries"}</span>
              </div>
              {expenses.length > 0 && <div className="search-box"><Icon name="search" size={16} /><input aria-label="Search expenses" placeholder="Search expenses..." value={query} onChange={(event) => setQuery(event.target.value)} /></div>}
              {isLoading && !hasLoaded ? (
                <div className="loading-state" role="status"><span className="spinner loading-spinner" />Loading your saved expenses…</div>
              ) : expenses.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-illustration"><Icon name="receipt" size={23} /></div>
                  <h3>A clean slate</h3>
                  <p>{hasLoaded ? "Your database has no expenses yet. Add one and it will still be here after you refresh." : "Connect to the backend to view saved expenses."}</p>
                  <button className="text-button" disabled={!hasLoaded || Boolean(dashboardError)} onClick={() => setIsExpenseOpen(true)}>Add your first expense <Icon name="arrow" size={15} /></button>
                </div>
              ) : filteredExpenses.length === 0 ? (
                <div className="filtered-empty">No expenses match “{query}”. Try another search.</div>
              ) : (
                <>
                  <div className="expense-table-wrap">
                    <table className="expense-table">
                      <thead><tr><th>EXPENSE</th><th>CATEGORY</th><th>DATE</th><th className="amount-cell">AMOUNT</th></tr></thead>
                      <tbody>{filteredExpenses.map((expense) => {
                        const color = getCategoryColor(expense.category, categories);
                        return <tr key={expense.id}>
                          <td><span className={`expense-avatar ${color}`}>{expense.title.trim().charAt(0).toUpperCase()}</span><span className="expense-title">{expense.title}</span></td>
                          <td><span className={`category-chip ${color}`}><span className="chip-dot" />{expense.category}</span></td>
                          <td className="date-cell">{formatDateTime(expense.created_at)}</td>
                          <td className="amount-cell expense-amount">−{formatCurrency(expense.amount)}</td>
                        </tr>;
                      })}</tbody>
                    </table>
                  </div>
                  <div className="mobile-expenses">{filteredExpenses.map((expense) => {
                    const color = getCategoryColor(expense.category, categories);
                    return <div className="mobile-expense" key={expense.id}><span className={`expense-avatar ${color}`}>{expense.title.trim().charAt(0).toUpperCase()}</span><div className="mobile-expense-copy"><strong>{expense.title}</strong><span>{expense.category} · {formatDateTime(expense.created_at)}</span></div><b>−{formatCurrency(expense.amount)}</b></div>;
                  })}</div>
                </>
              )}
            </div>

            <aside className="panel categories-panel" id="categories">
              <div className="panel-heading category-heading">
                <div><div className="section-kicker">SPENDING BY TYPE</div><h2>Categories</h2></div>
                <span className="category-total">{categories.length}</span>
              </div>
              <form className="category-form" onSubmit={addCategory} noValidate>
                <label className="sr-only" htmlFor="category-name">New category name</label>
                <input id="category-name" placeholder="Add a category..." value={categoryName} onChange={(event) => { setCategoryName(event.target.value); setCategoryError(""); setCategoryMessage(""); }} aria-describedby={categoryError ? "category-error" : categoryMessage ? "category-success" : undefined} />
                <button className="icon-button" type="submit" aria-label="Add category" disabled={isAddingCategory || !hasLoaded || Boolean(dashboardError)}><Icon name="plus" size={18} /></button>
              </form>
              {categoryError && <p className="form-feedback error-feedback" id="category-error" role="alert">{categoryError}</p>}
              {categoryMessage && <p className="form-feedback success-feedback" id="category-success" role="status">{categoryMessage}</p>}
              {isLoading && !hasLoaded ? <div className="category-loading">Loading categories…</div> : <div className="category-list">{categories.map((category, index) => (
                <div className="category-row" key={category.id}>
                  <span className={`category-icon ${categoryColors[index % categoryColors.length]}`}><Icon name={index % 2 === 0 ? "tag" : "wallet"} size={16} /></span>
                  <span className="category-name">{category.name}</span>
                  <span className="category-count">{category.total_expenses}</span>
                </div>
              ))}</div>}
              <div className="category-foot">Categories keep your spending organized.</div>
            </aside>
          </section>

          <footer className="page-footer"><span><span className="footer-dot" />All caught up</span><span>Ledger <span className="footer-separator">·</span> A clearer view of your spending</span></footer>
        </div>
      </main>

      <nav className="mobile-nav" aria-label="Mobile navigation">
        <button className={activeSection === "overview" ? "active" : ""} onClick={() => navigate("overview")}><Icon name="grid" size={20} /><span>Overview</span></button>
        <button className={activeSection === "expenses" ? "active" : ""} onClick={() => navigate("expenses")}><Icon name="receipt" size={20} /><span>Expenses</span></button>
        <button className={activeSection === "categories" ? "active" : ""} onClick={() => navigate("categories")}><Icon name="tag" size={20} /><span>Categories</span></button>
      </nav>

      {isExpenseOpen && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !isSubmitting) setIsExpenseOpen(false); }}>
        <section className="expense-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" onKeyDown={(event) => { if (event.key === "Escape" && !isSubmitting) setIsExpenseOpen(false); }}>
          <div className="modal-heading"><div><div className="section-kicker">NEW TRANSACTION</div><h2 id="modal-title">Add an expense</h2></div><button className="modal-close" type="button" onClick={() => setIsExpenseOpen(false)} aria-label="Close dialog"><Icon name="close" /></button></div>
          <p className="modal-description">Capture the details and we&apos;ll take it from here.</p>
          <form className="expense-form" onSubmit={addExpense} noValidate>
            <div className="field-group"><label htmlFor="expense-title">What was it for?</label><input id="expense-title" autoFocus placeholder="e.g. Lunch with friends" value={expenseTitle} onChange={(event) => { setExpenseTitle(event.target.value); setExpenseError(""); }} aria-describedby={expenseError ? "expense-error" : undefined} /></div>
            <div className="field-group"><label htmlFor="expense-amount">Amount</label><div className="amount-input"><span>₹</span><input id="expense-amount" type="number" inputMode="decimal" min="0.01" step="0.01" placeholder="0.00" value={expenseAmount} onChange={(event) => { setExpenseAmount(event.target.value); setExpenseError(""); }} /></div></div>
            <div className="field-group"><label htmlFor="expense-category">Category</label><select id="expense-category" value={expenseCategory} onChange={(event) => { setExpenseCategory(event.target.value); setExpenseError(""); }} disabled={categories.length === 0}><option value="">Choose a category</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select>{categories.length === 0 && <span className="field-hint">Create a category first to add an expense.</span>}</div>
            {expenseError && <p className="form-feedback error-feedback modal-error" id="expense-error" role="alert">{expenseError}</p>}
            <div className="modal-actions"><button className="button button-secondary" type="button" onClick={() => setIsExpenseOpen(false)} disabled={isSubmitting}>Cancel</button><button className="button button-primary" type="submit" disabled={isSubmitting || categories.length === 0}>{isSubmitting ? <><span className="spinner" />Adding…</> : <><Icon name="plus" size={17} />Add expense</>}</button></div>
          </form>
          <div className="demo-disclaimer"><span className="demo-dot" />Saved to SQLite — your expense stays after refresh.</div>
        </section>
      </div>}
    </div>
  );
}
