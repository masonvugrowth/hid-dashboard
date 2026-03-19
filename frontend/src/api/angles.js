import axios from "axios";
const BASE = "/api/creative-angles";
export const listAngles = (params = {}) => axios.get(BASE, { params }).then(r => r.data.data);
export const getAngle = (id) => axios.get(`${BASE}/${id}`).then(r => r.data.data);
export const createAngle = (data) => axios.post(BASE, data).then(r => r.data.data);
export const updateAngle = (id, data) => axios.patch(`${BASE}/${id}`, data).then(r => r.data.data);
