export const normalizeApiBaseUrl = (url) =>
  (url || '').trim().replace(/\/+$/, '');
