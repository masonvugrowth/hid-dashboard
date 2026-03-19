import axios from "axios";
const BASE = "/api/kol-records";
export const listKolRecords = (params = {}) => axios.get(BASE, { params }).then(r => r.data.data);
