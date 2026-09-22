import { apiClient } from './api';

export const incidentApi = {
  getIncidents: async () => {
    return apiClient.get('/incidents');
  },

  logHitAndRun: async (incidentPayload) => {
    return apiClient.post('/incident/hit-and-run', incidentPayload);
  },

  broadcastPoliceAlert: async (incidentId, channel = 'GCTP_ALL_SECTORS') => {
    return apiClient.post(`/incident/${incidentId}/broadcast`, { channel });
  }
};
