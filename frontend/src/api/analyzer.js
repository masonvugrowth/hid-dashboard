import axios from "axios";
const BASE = "/api/ad-analyzer";

export const analyzeSingle = (combo_id) =>
  axios.post(`${BASE}/analyze`, { combo_id }).then(r => r.data.data);

export const analyzeBatch = (branch_id, force_reanalyze = false) =>
  axios.post(`${BASE}/analyze-batch`, { branch_id, force_reanalyze }).then(r => r.data.data);

export const listResults = (params = {}) =>
  axios.get(`${BASE}/results`, { params }).then(r => r.data.data);

export const getInsights = (params = {}) =>
  axios.get(`${BASE}/insights`, { params }).then(r => r.data.data);
