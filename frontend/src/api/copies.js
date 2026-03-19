import axios from "axios";
const BASE = "/api/copies";
export const listCopies = (params = {}) => axios.get(BASE, { params }).then(r => r.data.data);
export const getCopy = (id) => axios.get(`${BASE}/${id}`).then(r => r.data.data);
export const createCopy = (data) => axios.post(BASE, data).then(r => r.data.data);
export const updateCopy = (id, data) => axios.patch(`${BASE}/${id}`, data).then(r => r.data.data);
export const deleteCopy = (id) => axios.delete(`${BASE}/${id}`).then(r => r.data.data);
