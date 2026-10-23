import type {
  Category,
  CreatedCategory,
  CreatedExpense,
  CreateCategoryRequest,
  CreateExpenseRequest,
  Expense,
  ExpenseSummary,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(new URL(path, API_BASE_URL), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch {
    throw new Error("Could not connect to the expense service. Check your connection and try again.");
  }

  if (!response.ok) {
    const responseText = await response.text();
    let message = responseText;
    try {
      const body: unknown = JSON.parse(responseText);
      if (
        typeof body === "object" &&
        body !== null &&
        "detail" in body &&
        typeof body.detail === "string"
      ) {
        message = body.detail;
      }
    } catch {
      message = responseText;
    }
    throw new Error(message || `The expense service returned ${response.status}.`);
  }

  return (await response.json()) as T;
}

export const expenseApi = {
  getCategories: () => request<Category[]>("/categories"),
  createCategory: (data: CreateCategoryRequest) =>
    request<CreatedCategory>("/categories", { method: "POST", body: JSON.stringify(data) }),
  getExpenses: () => request<Expense[]>("/expenses"),
  createExpense: (data: CreateExpenseRequest) =>
    request<CreatedExpense>("/expenses", { method: "POST", body: JSON.stringify(data) }),
  getSummary: () => request<ExpenseSummary>("/summary"),
};
