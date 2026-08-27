import axios from "axios";
const BASE = "/api/marketing-activity";

export const getMarketingActivitySummary = (params = {}) =>
  axios.get(`${BASE}/summary`, { params }).then(r => r.data.data);

export const getCRMBranchComparison = (params = {}) =>
  axios.get(`${BASE}/crm-branch-comparison`, { params }).then(r => r.data.data);

// Hand-typed rate plan → campaign labels, shown next to Rate Plan Name on the
// CRM Reservations tab. Returns a flat { [rate_plan_name]: campaign_name } map.
export const getRatePlanCampaigns = () =>
  axios.get(`${BASE}/rate-plan-campaigns`).then(r => r.data.data);

// Empty campaign_name clears the label.
export const saveRatePlanCampaign = (rate_plan_name, campaign_name) =>
  axios.put(`${BASE}/rate-plan-campaigns`, { rate_plan_name, campaign_name })
    .then(r => r.data.data);
