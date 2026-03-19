import axios from "axios";
const BASE = "/api/materials";
export const listMaterials = (params = {}) => axios.get(BASE, { params }).then(r => r.data.data);
export const getMaterial = (id) => axios.get(`${BASE}/${id}`).then(r => r.data.data);
export const createMaterial = (data) => axios.post(BASE, data).then(r => r.data.data);
export const updateMaterial = (id, data) => axios.patch(`${BASE}/${id}`, data).then(r => r.data.data);
export const deleteMaterial = (id) => axios.delete(`${BASE}/${id}`).then(r => r.data.data);
