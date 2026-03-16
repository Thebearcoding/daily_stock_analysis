import axios from 'axios';
import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  FundAdviceResponse,
  FundTaskAccepted,
  FundTaskListResponse,
  FundTaskStatus,
  FundHistoryListResponse,
  FundHistoryDetailResponse,
} from '../types/funds';

export type FundAdviceMode = 'fast' | 'deep';

export const fundsApi = {
  // ── 1. Stateless preview (unchanged) ──

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

  // ── 2. Analyze with persist (sync / async) ──

  analyze: async (
    fundCode: string,
    days = 120,
    mode: FundAdviceMode = 'fast',
    asyncMode = false,
  ): Promise<FundTaskAccepted | Record<string, unknown>> => {
    const code = fundCode.trim();
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/funds/analyze',
      null,
      {
        params: { fund_code: code, days, mode, async_mode: asyncMode },
        timeout: asyncMode ? 10000 : 180000,
      },
    );
    return toCamelCase<FundTaskAccepted | Record<string, unknown>>(response.data);
  },

  // ── 3. Task status / list ──

  getTaskStatus: async (taskId: string): Promise<FundTaskStatus> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/funds/status/${taskId}`,
    );
    return toCamelCase<FundTaskStatus>(response.data);
  },

  getTaskList: async (limit = 20): Promise<FundTaskListResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/funds/tasks',
      { params: { limit } },
    );
    return toCamelCase<FundTaskListResponse>(response.data);
  },

  // ── 4. History list / detail ──

  getHistoryList: async (params: {
    fundCode?: string;
    page?: number;
    limit?: number;
  } = {}): Promise<FundHistoryListResponse> => {
    const { fundCode, page = 1, limit = 20 } = params;
    const queryParams: Record<string, string | number> = { page, limit };
    if (fundCode) queryParams.fund_code = fundCode;

    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/funds/history',
      { params: queryParams },
    );
    return toCamelCase<FundHistoryListResponse>(response.data);
  },

  getHistoryDetail: async (recordId: number): Promise<FundHistoryDetailResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/funds/history/${recordId}`,
    );
    return toCamelCase<FundHistoryDetailResponse>(response.data);
  },
};
