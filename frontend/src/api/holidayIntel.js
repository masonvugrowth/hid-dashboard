import axios from "axios";
const BASE = "/api/holiday-intel";
export const getSeasonMatrix = () => axios.get(`${BASE}/season-matrix`).then(r => r.data.data);
export const getCountryHolidays = (code) => axios.get(`${BASE}/country/${code}`).then(r => r.data.data);
export const getMonthOpportunities = (month) => axios.get(`${BASE}/month/${month}`).then(r => r.data.data);
export const getUpcomingWindows = () => axios.get(`${BASE}/upcoming`).then(r => r.data.data);
export const getCrossReference = (code, month) => axios.get(`${BASE}/cross-reference`, { params: { country_code: code, month } }).then(r => r.data.data);
export const triggerRecompute = () => axios.post(`${BASE}/recompute`).then(r => r.data.data);
