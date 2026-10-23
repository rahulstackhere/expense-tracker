export interface Category {
  id: number;
  name: string;
  total_expenses: number;
}

export interface Expense {
  id: number;
  title: string;
  amount: number;
  category_id?: number;
  category: string;
  created_at: string;
}

export interface ExpenseSummary {
  total: number;
  count: number;
  average: number;
}

export interface CreateCategoryRequest {
  name: string;
}

export interface CreatedCategory {
  id: number;
  name: string;
}

export interface CreateExpenseRequest {
  title: string;
  amount: number;
  category_id: number;
}

export interface CreatedExpense extends CreateExpenseRequest {
  id: number;
  created_at: string;
}
