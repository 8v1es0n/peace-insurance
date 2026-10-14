import type {
  ChatHistory,
  ChatThread,
  InsuranceCategory,
  PlanInterrupt,
  Product,
} from './types';

export const API_BASE = '/api/v1';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(error?.message ?? '请求失败，请稍后重试', response.status);
  }
  return response.json() as Promise<T>;
}

async function authorizedBusinessRequest<T>(
  path: string,
  userId: number,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'x-user-id': String(userId),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(error?.message ?? '璇锋眰澶辫触锛岃绋嶅悗閲嶈瘯', response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function agentRequest<T>(
  path: string,
  userId: number,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'x-user-id': String(userId),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(error?.detail ?? error?.message ?? '请求失败，请稍后重试', response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function listProducts(
  category: InsuranceCategory | 'all',
  signal?: AbortSignal,
): Promise<Product[]> {
  const params = new URLSearchParams();
  if (category !== 'all') {
    params.set('category', category);
  }
  const query = params.toString();
  return request<Product[]>(`/products${query ? `?${query}` : ''}`, { signal });
}

export function markPlanItemInsured(
  userId: number,
  planId: string,
  itemId: string,
): Promise<unknown> {
  return authorizedBusinessRequest<unknown>(
    `/insurance-plans/${encodeURIComponent(planId)}/items/${encodeURIComponent(itemId)}/insured`,
    userId,
    { method: 'PATCH' },
  );
}

export function getInsurancePlan(userId: number, planId: string): Promise<unknown> {
  return authorizedBusinessRequest<unknown>(
    `/insurance-plans/${encodeURIComponent(planId)}`,
    userId,
  );
}

export function listChatThreads(userId: number): Promise<ChatThread[]> {
  return agentRequest<ChatThread[]>('/chat-threads', userId);
}

export function createChatThread(userId: number, title = '保险咨询'): Promise<ChatThread> {
  return agentRequest<ChatThread>('/chat-threads', userId, {
    method: 'POST',
    body: JSON.stringify({ title }),
  });
}

export function getChatHistory(userId: number, threadId: string): Promise<ChatHistory> {
  return agentRequest<ChatHistory>(`/chat-threads/${threadId}/messages`, userId);
}

export function renameChatThread(
  userId: number,
  threadId: string,
  title: string,
): Promise<ChatThread> {
  return agentRequest<ChatThread>(`/chat-threads/${threadId}`, userId, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });
}

export async function deleteChatThread(userId: number, threadId: string): Promise<void> {
  await agentRequest<void>(`/chat-threads/${threadId}`, userId, {
    method: 'DELETE',
  });
}

export async function streamChat(
  userId: number,
  threadId: string,
  input: { message?: string; decision?: Record<string, unknown> },
  handlers: {
    onMessage: (chunk: string) => void;
    onAdditionalInfo?: (info: unknown) => void;
    onInterrupt?: (interrupt: PlanInterrupt) => void;
  },
): Promise<void> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-user-id': String(userId),
    },
    body: JSON.stringify({ thread_id: threadId, ...input }),
  });
  if (!response.ok || !response.body) {
    const error = await response.json().catch(() => null);
    throw new ApiError(error?.detail ?? error?.message ?? '消息发送失败，请稍后重试', response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() ?? '';
    parts.forEach((eventText) => handleSseEvent(eventText, handlers));
  }
  if (buffer.trim()) {
    handleSseEvent(buffer, handlers);
  }
}

function handleSseEvent(
  eventText: string,
  handlers: {
    onMessage: (chunk: string) => void;
    onAdditionalInfo?: (info: unknown) => void;
    onInterrupt?: (interrupt: PlanInterrupt) => void;
  },
) {
  const lines = eventText.split(/\r?\n/);
  const event = lines.find((line) => line.startsWith('event:'))?.slice(6).trim();
  const data = lines
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n');
  if (!data) return;
  if (event === 'message') {
    handlers.onMessage(parseSseMessage(data));
    return;
  }
  if (event === 'interrupt') {
    const interrupt = parseInterrupt(data);
    if (interrupt) handlers.onInterrupt?.(interrupt);
    return;
  }
  if (event === 'additional_info') {
    handlers.onAdditionalInfo?.(parseJsonLike(data) ?? data);
  }
}

function parseSseMessage(data: string): string {
  try {
    const value = JSON.parse(data) as unknown;
    return typeof value === 'string' ? value : JSON.stringify(value);
  } catch {
    return data;
  }
}

function parseInterrupt(data: string): PlanInterrupt | null {
  const parsed = parseJsonLike(data);
  const value = Array.isArray(parsed) ? parsed[0] : parsed;
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Partial<PlanInterrupt>;
  if (!('plan' in candidate) || typeof candidate.confirm_info !== 'string') return null;
  return {
    plan: candidate.plan,
    confirm_info: candidate.confirm_info,
    action: Array.isArray(candidate.action)
      ? candidate.action.filter((item): item is 'approve' | 'reject' =>
          item === 'approve' || item === 'reject',
        )
      : ['approve', 'reject'],
  };
}

function parseJsonLike(data: string): unknown {
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}
