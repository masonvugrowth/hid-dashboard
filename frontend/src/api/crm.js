import axios from "axios";
const BASE = "/api/crm";

export const getCRMSummary = (params = {}) =>
  axios.get(`${BASE}/summary`, { params }).then(r => r.data.data);

export const getCRMDaily = (params = {}) =>
  axios.get(`${BASE}/daily`, { params }).then(r => r.data.data);

export const getCRMMonthly = (params = {}) =>
  axios.get(`${BASE}/monthly`, { params }).then(r => r.data.data);

export const getCRMByBranch = (params = {}) =>
  axios.get(`${BASE}/by-branch`, { params }).then(r => r.data.data);

export const getCRMBySource = (params = {}) =>
  axios.get(`${BASE}/by-source`, { params }).then(r => r.data.data);

export const getCRMReservations = (params = {}) =>
  axios.get(`${BASE}/reservations`, { params }).then(r => r.data.data);

export const getCRMRoomTypes = (params = {}) =>
  axios.get(`${BASE}/room-types`, { params }).then(r => r.data.data);
