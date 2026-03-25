import axios from "axios";
const BASE = "/api/email-marketing";

export const getEmailSummary = (params = {}) =>
  axios.get(`${BASE}/summary`, { params }).then(r => r.data.data);

export const getEmailDaily = (params = {}) =>
  axios.get(`${BASE}/daily`, { params }).then(r => r.data.data);

export const getEmailByWorkflow = (params = {}) =>
  axios.get(`${BASE}/by-workflow`, { params }).then(r => r.data.data);
