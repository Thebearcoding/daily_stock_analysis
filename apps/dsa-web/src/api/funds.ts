import axios from 'axios';
import apiClient from './index';
import { toCamelCase } from './utils';
import type { FundAdviceResponse } from '../types/funds';

export type FundAdviceMode = 'fast' | 'deep';

export const fundsApi = {
  getAdvice: async (
    fundCode: string,
    days = 120,
    mode: FundAdviceMode = 'fast',
  ): Promise<FundAdviceResponse> => {
    const code = fundCode.trim();
    try {
      const response = await apiClient.get<Record<string, unknown>>(
        `/api/v1/funds/${code}/advice`,
        {
          params: { days, mode },
          timeout: mode === 'deep' ? 180000 : 60000,
        },
      );

      return toCamelCase<FundAdviceResponse>(response.data);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string' && detail) {
          throw new Error(detail);
        }
        if (detail && typeof detail === 'object') {
          const message = (detail as { message?: unknown }).message;
          if (typeof message === 'string' && message) {
            throw new Error(message);
          }
        }
        if (error.response?.status) {
          throw new Error(`请求失败（${error.response.status}）`);
        }
      }
      throw error;
    }
  },
};
