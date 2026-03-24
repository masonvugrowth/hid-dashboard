import axios from "axios";
const BASE = "/api/email-marketing";

export const getEmailSummary = (params = {}) =>
  axios.get(`${BASE}/summary`, { params }).then(r => r.data.data);

export const getEmailDaily = (params = {}) =>
  axios.get(`${BASE}/daily`, { params }).then(r => r.data.data);

export const getEmailByWorkflow = (params = {}) =>
  axios.get(`${BASE}/by-workflow`, { params }).then(r => r.data.data);

export const getEmailEvents = (params = {}) =>
  axios.get(`${BASE}/events`, { params }).then(r => r.data.data);

export const getEmailWorkflowEvents = (workflowId, params = {}) =>
  axios.get(`${BASE}/workflow/${workflowId}/events`, { params }).then(r => r.data.data);

export const triggerAggregation = (params = {}) =>
  axios.post(`${BASE}/aggregate`, null, { params }).then(r => r.data.data);
