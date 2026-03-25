import axios from "axios";
const BASE = "/api/email-marketing";

export const getEmailSummary = (params = {}) =>
  axios.get(`${BASE}/summary`, { params }).then(r => r.data.data);

export const getEmailDaily = (params = {}) =>
  axios.get(`${BASE}/daily`, { params }).then(r => r.data.data);

export const getEmailByCampaign = (params = {}) =>
  axios.get(`${BASE}/by-campaign`, { params }).then(r => r.data.data);
