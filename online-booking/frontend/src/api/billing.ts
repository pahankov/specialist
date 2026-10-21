import apiClient from './http';

export type BillingStatus = 'trial' | 'active' | 'readonly' | 'paused' | 'suspended';

export interface BillingInvoice {
  id: number;
  period_index: number;
  amount: number;
  credits_applied: number;
  paid_amount: number;
  due_amount: number;
  status: 'open' | 'paid' | 'void' | string;
  status_label: string;
  issue_at: string;
  due_at: string;
  paid_at?: string | null;
  payment_method?: string | null;
  note?: string | null;
  period_start?: string | null;
  period_end?: string | null;
}

export interface BillingCredit {
  id: number;
  source: 'client_bonus' | 'referral_bonus' | 'manual' | string;
  source_label: string;
  amount: number;
  remaining: number;
  expires_at?: string | null;
  note?: string | null;
  created_at?: string | null;
}

export interface ClientBonusInfo {
  eligible_count: number;
  max_count: number;
  amount: number;
  max_amount: number;
  status: 'pending' | 'credited' | 'rejected' | 'blocked' | string;
  total_candidates: number;
  unconfirmed_count: number;
  prompted_count: number;
  unconfirmed_ratio: number;
  review_flag: boolean;
  evaluated_at?: string | null;
  evaluation_at?: string | null;
}

export interface ReferralRow {
  id: number;
  referred_name: string;
  registered_at?: string | null;
  status: 'pending' | 'qualified' | 'rejected' | string;
  status_label: string;
  qualified_count: number;
  required_count: number;
  amount: number;
  reject_reason?: string | null;
  evaluated_at?: string | null;
}

export interface BillingSummary {
  master_id: number;
  master_name: string;
  access_status: BillingStatus;
  access_status_label: string;
  is_blocked: boolean;
  trial_started_at: string;
  trial_ends_at: string;
  billing_started_at: string;
  trial_days_left: number;
  review_flag: boolean;
  bonus_blocked_until?: string | null;
  referral_code: string;
  referral_link: string;
  next_payment_at: string;
  next_payment_amount: number;
  balance: { due: number; credit: number; net: number };
  invoices: BillingInvoice[];
  credits: BillingCredit[];
  client_bonus: ClientBonusInfo;
  referral: {
    qualified_count: number;
    max_count: number;
    bonus_total: number;
    max_amount: number;
    click_days: number;
    credit_days: number;
  };
  referrals: ReferralRow[];
  payment_instructions: string;
}

export interface BillingOverviewRow {
  master_id: number;
  master_name: string;
  email?: string | null;
  access_status: BillingStatus;
  access_status_label: string;
  trial_ends_at?: string | null;
  balance_due: number;
  balance_credit: number;
  review_flag: boolean;
  referral_code: string;
}

export interface BillingOverview {
  items: BillingOverviewRow[];
  status_labels: Record<string, string>;
  total: number;
  summary: {
    due: number;
    credit: number;
    readonly: number;
    paused: number;
    review: number;
  };
}

export const billingApi = {
  my() {
    return apiClient.get<BillingSummary>('/api/v1/admin/billing/me');
  },
  overview(params?: { search?: string; status?: string }) {
    return apiClient.get<BillingOverview>('/api/v1/admin/billing/overview', { params });
  },
  adminGet(masterId: number) {
    return apiClient.get<BillingSummary>(`/api/v1/admin/billing/masters/${masterId}`);
  },
  payInvoice(invoiceId: number, data?: { amount?: number; method?: string; note?: string }) {
    return apiClient.post<{ ok: boolean; invoice_id: number; billing: BillingSummary }>(
      `/api/v1/admin/billing/invoices/${invoiceId}/pay`,
      data ?? {},
    );
  },
  addCredit(masterId: number, data: { amount: number; note?: string }) {
    return apiClient.post<{ ok: boolean; credit_id: number; billing: BillingSummary }>(
      `/api/v1/admin/billing/masters/${masterId}/credits`,
      data,
    );
  },
  reviewAction(masterId: number, action: 'clear' | 'block', note?: string) {
    return apiClient.post<{ ok: boolean; billing: BillingSummary }>(
      `/api/v1/admin/billing/masters/${masterId}/review`,
      { action, note },
    );
  },
  tick(masterId: number) {
    return apiClient.post<{ ok: boolean; billing: BillingSummary }>(
      `/api/v1/admin/billing/masters/${masterId}/tick`,
    );
  },
};

export const referralApi = {
  click(code: string) {
    return apiClient.post<{
      token: string;
      expires_at: string;
      master_name: string;
      referral_code: string;
    }>(`/api/v1/referrals/click/${code}`);
  },
  attribute(clickToken: string) {
    return apiClient.post<{ status: string; referral_id?: number; reason?: string }>(
      '/api/v1/referrals/attribute',
      { click_token: clickToken },
    );
  },
  my() {
    return apiClient.get<{
      code: string;
      link: string;
      qualified_count: number;
      max_count: number;
      bonus_total: number;
      max_amount: number;
      click_days: number;
      credit_days: number;
      referrals: ReferralRow[];
    }>('/api/v1/referrals/my');
  },
};
