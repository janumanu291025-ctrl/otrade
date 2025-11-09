import axios from "axios";
const BASE_URL = "http://localhost:8000/api";
const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json"
  }
});
const brokerAPI = {
  getConfig: (brokerType) => api.get(`/broker/config/${brokerType}`),
  createConfig: (data) => api.post("/broker/config", data),
  initConfig: (brokerType) => api.post(`/broker/init/${brokerType}`),
  getAuthUrl: (brokerType) => api.get(`/broker/auth-url/${brokerType}`),
  getProfile: (brokerType) => api.get(`/broker/profile/${brokerType}`),
  getFunds: (brokerType) => api.get(`/broker/funds/${brokerType}`),
  downloadInstruments: (brokerType, exchange = null) => api.post(`/broker/instruments/download/${brokerType}`, null, { params: exchange ? { exchange } : {} }),
  getInstruments: (params = {}) => api.get("/broker/instruments", { params }),
  getInstrumentsStats: () => api.get("/broker/instruments/stats"),
  getQuote: (brokerType, instruments) => {
    const instrumentsStr = Array.isArray(instruments) ? instruments.join(",") : instruments;
    return api.get(`/broker/quote/${brokerType}`, {
      params: { instruments: instrumentsStr }
    });
  },
  disconnect: (brokerType) => api.post(`/broker/disconnect/${brokerType}`),
  getStatus: (brokerType) => api.get(`/broker/status/${brokerType}`),
  getEnvConfig: (brokerType) => api.get(`/broker/env-config/${brokerType}`),
  updateEnvConfig: (brokerType, data) => api.post(`/broker/env-config/${brokerType}`, data),
  getNifty50: () => api.get("/broker/nifty50")
};
export {
  brokerAPI as b
};
