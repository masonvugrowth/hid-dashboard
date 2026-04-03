import axios from "axios";
const BASE = "/api/marketing-activity";

export const getMarketingActivitySummary = (params = {}) =>
  axios.get(`${BASE}/summary`, { params }).then(r => r.data.data);
