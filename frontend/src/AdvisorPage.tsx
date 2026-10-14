import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CustomerServiceOutlined,
  DeleteOutlined,
  EditOutlined,
  MessageOutlined,
  FilePdfOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
  SendOutlined,
  ShoppingCartOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { Alert, Button, Drawer, Empty, Input, Modal, Popconfirm, Spin } from 'antd';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { attachInfoToLastAssistantMessage, normalizeAdditionalInfo } from './additionalInfo';
import {
  ApiError,
  createChatThread,
  deleteChatThread,
  getChatHistory,
  getInsurancePlan,
  listChatThreads,
  renameChatThread,
  streamChat,
} from './api';
import { formatCategoryLabel } from './categoryLabels';
import { MarkdownMessage } from './MarkdownMessage';
import type { AdditionalInfo, AdditionalPolicy, AdditionalProduct, AuthSession, ClauseSource, PlanInterrupt } from './types';
import type { ChatMessage, ChatThread } from './types';

interface AdvisorPageProps {
  session: AuthSession;
  onBack: () => void;
  onSessionExpired: () => void;
  onApplyProduct: (target: ApplyProductTarget) => void;
}

interface ApplyProductTarget {
  productId: string;
  planId: string;
  itemId: string;
}

export function AdvisorPage({ session, onBack, onSessionExpired, onApplyProduct }: AdvisorPageProps) {
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loadingThreads, setLoadingThreads] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingInterrupt, setPendingInterrupt] = useState<PlanInterrupt | null>(null);
  const [renamingThread, setRenamingThread] = useState<ChatThread | null>(null);
  const [renameTitle, setRenameTitle] = useState('');
  const [rejectReasonOpen, setRejectReasonOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [selectedSource, setSelectedSource] = useState<SelectedSource | null>(null);
  const [planItemStatuses, setPlanItemStatuses] = useState<Record<string, ProductPlanStatus>>({});
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const userId = session.user.id;
  const planIdsKey = useMemo(
    () => collectPlanIds(messages, pendingInterrupt).join('|'),
    [messages, pendingInterrupt],
  );

  const loadMessages = useCallback(async (threadId: string) => {
    setLoadingMessages(true);
    setError(null);
    try {
      const history = await getChatHistory(userId, threadId);
      setMessages(normalizeHistoryMessages(history.messages));
      setPendingInterrupt(history.interrupt);
    } catch (reason) {
      if (isUnauthorized(reason)) {
        onSessionExpired();
        return;
      }
      setError(reason instanceof Error ? reason.message : '会话历史加载失败');
    } finally {
      setLoadingMessages(false);
    }
  }, [onSessionExpired, userId]);

  const openThread = useCallback(async (threadId: string) => {
    setActiveThreadId(threadId);
    await loadMessages(threadId);
  }, [loadMessages]);

  const createThread = useCallback(async () => {
    const thread = await createChatThread(userId);
    setThreads((current) => [thread, ...current]);
    setActiveThreadId(thread.id);
    setMessages([]);
    setPendingInterrupt(null);
    return thread;
  }, [userId]);

  async function startNewThread() {
    setError(null);
    try {
      await createThread();
    } catch (reason) {
      if (isUnauthorized(reason)) {
        onSessionExpired();
        return;
      }
      setError(reason instanceof Error ? reason.message : '新建会话失败');
    }
  }

  async function renameThread() {
    if (!renamingThread) return;
    const title = renameTitle.trim();
    if (!title) return;
    setError(null);
    try {
      const updated = await renameChatThread(userId, renamingThread.id, title);
      setThreads((current) =>
        current.map((thread) => (thread.id === updated.id ? updated : thread)),
      );
      setRenamingThread(null);
      setRenameTitle('');
    } catch (reason) {
      if (isUnauthorized(reason)) {
        onSessionExpired();
        return;
      }
      setError(reason instanceof Error ? reason.message : '重命名会话失败');
    }
  }

  async function deleteThread(threadId: string) {
    setError(null);
    try {
      await deleteChatThread(userId, threadId);
      const nextThreads = threads.filter((thread) => thread.id !== threadId);
      setThreads(nextThreads);
      if (activeThreadId === threadId) {
        const nextActive = nextThreads[0];
        setActiveThreadId(nextActive?.id ?? null);
        setMessages([]);
        setPendingInterrupt(null);
        if (nextActive) await loadMessages(nextActive.id);
      }
    } catch (reason) {
      if (isUnauthorized(reason)) {
        onSessionExpired();
        return;
      }
      setError(reason instanceof Error ? reason.message : '删除会话失败');
    }
  }

  useEffect(() => {
    let ignore = false;
    async function loadThreads() {
      setLoadingThreads(true);
      setError(null);
      try {
        const loaded = await listChatThreads(userId);
        if (ignore) return;
        if (loaded.length === 0) {
          const thread = await createChatThread(userId);
          if (ignore) return;
          setThreads([thread]);
          setActiveThreadId(thread.id);
          setMessages([]);
          setPendingInterrupt(null);
          return;
        }
        setThreads(loaded);
        setActiveThreadId(loaded[0].id);
        await loadMessages(loaded[0].id);
      } catch (reason) {
        if (!ignore) {
          if (isUnauthorized(reason)) {
            onSessionExpired();
            return;
          }
          setError(reason instanceof Error ? reason.message : '会话加载失败');
        }
      } finally {
        if (!ignore) setLoadingThreads(false);
      }
    }
    void loadThreads();
    return () => {
      ignore = true;
    };
  }, [loadMessages, onSessionExpired, userId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, sending]);

  useEffect(() => {
    const planIds = planIdsKey ? planIdsKey.split('|') : [];
    if (planIds.length === 0) {
      setPlanItemStatuses({});
      return;
    }

    let ignore = false;
    async function refreshPlanItemStatuses() {
      try {
        const plans = await Promise.all(planIds.map((planId) => getInsurancePlan(userId, planId)));
        if (!ignore) setPlanItemStatuses(mergePlanItemStatuses(plans));
      } catch (reason) {
        if (ignore) return;
        if (isUnauthorized(reason)) {
          onSessionExpired();
        }
      }
    }

    void refreshPlanItemStatuses();
    return () => {
      ignore = true;
    };
  }, [onSessionExpired, planIdsKey, userId]);

  async function sendMessage() {
    const content = input.trim();
    if (!content || sending) return;
    setInput('');
    setSending(true);
    setError(null);
    setPendingInterrupt(null);
    try {
      const threadId = activeThreadId ?? (await createThread()).id;
      setMessages((current) => [
        ...current,
        { role: 'user', content },
        { role: 'assistant', content: '' },
      ]);
      await streamChat(userId, threadId, { message: content }, {
        onMessage: appendAssistantChunk,
        onAdditionalInfo: appendAdditionalInfo,
        onInterrupt: (interrupt) => {
          setPendingInterrupt(interrupt);
          removeEmptyAssistantMessage();
        },
      });
      setThreads((current) =>
        current.map((thread) =>
          thread.id === threadId
            ? { ...thread, title: thread.title === '保险咨询' ? content.slice(0, 20) : thread.title }
            : thread,
        ),
      );
    } catch (reason) {
      if (isUnauthorized(reason)) {
        onSessionExpired();
        return;
      }
      setError(reason instanceof Error ? reason.message : '消息发送失败');
      setMessages((current) => current.filter((item) => item.content !== ''));
    } finally {
      setSending(false);
    }
  }

  async function submitDecision(action: 'approve' | 'reject', reason?: string) {
    if (!activeThreadId || sending) return;
    const decision =
      action === 'approve'
        ? { action: 'approve' }
        : { action: 'reject', reject_reason: reason?.trim() || '用户未填写原因' };
    setPendingInterrupt(null);
    setSending(true);
    setError(null);
    setMessages((current) => [
      ...current,
      {
        role: 'user',
        content: action === 'approve' ? '确认保存保险方案' : '取消保存保险方案',
      },
      { role: 'assistant', content: '' },
    ]);
    try {
      await streamChat(userId, activeThreadId, { decision }, {
        onMessage: appendAssistantChunk,
        onAdditionalInfo: appendAdditionalInfo,
        onInterrupt: (interrupt) => {
          setPendingInterrupt(interrupt);
          removeEmptyAssistantMessage();
        },
      });
    } catch (reason) {
      if (isUnauthorized(reason)) {
        onSessionExpired();
        return;
      }
      setError(reason instanceof Error ? reason.message : '操作提交失败');
      removeEmptyAssistantMessage();
    } finally {
      setSending(false);
    }
  }

  function appendAssistantChunk(chunk: string) {
    setMessages((current) => {
      const next = [...current];
      const last = next[next.length - 1];
      if (last?.role === 'assistant') {
        next[next.length - 1] = { ...last, content: last.content + chunk };
      }
      return next;
    });
  }

  function appendAdditionalInfo(raw: unknown) {
    const info = normalizeAdditionalInfo(raw);
    setMessages((current) => attachInfoToLastAssistantMessage(current, info));
  }

  function removeEmptyAssistantMessage() {
    setMessages((current) => {
      const last = current[current.length - 1];
      if (last?.role === 'assistant' && last.content === '') {
        return current.slice(0, -1);
      }
      return current;
    });
  }

  return (
    <div className="advisor-page">
      <header className="advisor-header">
        <div className="brand">
          <span className="brand__mark"><SafetyCertificateOutlined /></span>
          <span><strong>安心保</strong><small>智能顾问</small></span>
        </div>
        <div>
          <span>{session.user.displayName || session.user.username}</span>
          <Button icon={<ArrowLeftOutlined />} onClick={onBack}>返回商城</Button>
        </div>
      </header>
      <main className="advisor-workspace">
        <aside className="thread-panel">
          <Button block type="primary" icon={<PlusOutlined />} onClick={() => void startNewThread()}>
            新建咨询
          </Button>
          <div className="thread-list">
            {loadingThreads ? <Spin /> : null}
            {!loadingThreads && threads.length === 0 ? <Empty description="暂无会话" /> : null}
            {threads.map((thread) => (
              <div
                className={thread.id === activeThreadId ? 'thread-item is-active' : 'thread-item'}
                key={thread.id}
              >
                <button type="button" onClick={() => void openThread(thread.id)}>
                  <MessageOutlined />
                  <span className="thread-text">
                    <strong>{thread.title}</strong>
                    <small>{formatThreadTime(thread.created_at)}</small>
                  </span>
                </button>
                <div className="thread-actions">
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => {
                      setRenamingThread(thread);
                      setRenameTitle(thread.title);
                    }}
                  />
                  <Popconfirm
                    title="删除会话"
                    description="删除后会同时清理该会话的历史状态。"
                    okText="删除"
                    cancelText="取消"
                    onConfirm={() => void deleteThread(thread.id)}
                  >
                    <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                  </Popconfirm>
                </div>
              </div>
            ))}
          </div>
        </aside>

        <section className="chat-panel">
          {error ? <Alert className="chat-alert" type="error" showIcon message={error} /> : null}
          <div className="chat-scroll">
            {loadingMessages ? (
              <div className="chat-loading"><Spin /></div>
            ) : messages.length === 0 ? (
              <div className="chat-empty">
                <CustomerServiceOutlined />
                <h1>你好，我是安心保智能顾问</h1>
                <p>告诉我你的年龄、职业、预算和关注的保障类型，我会协助你梳理保险方案。</p>
              </div>
            ) : (
              messages.map((message, index) => (
                <div className={`chat-message chat-message--${message.role}`} key={`${message.role}-${index}`}>
                  <div>
                    {message.content ? (
                      <MessageContent
                        message={message}
                        onApplyProduct={onApplyProduct}
                        planItemStatuses={planItemStatuses}
                        onSourceClick={(source, answerContent) =>
                          setSelectedSource({ source, answerContent })
                        }
                      />
                    ) : '正在整理回复...'}
                  </div>
                </div>
              ))
            )}
            {pendingInterrupt ? (
              <PlanInterruptCard
                interrupt={pendingInterrupt}
                loading={sending}
                onApprove={() => void submitDecision('approve')}
                onReject={() => {
                  setRejectReason('');
                  setRejectReasonOpen(true);
                }}
                onApplyProduct={onApplyProduct}
                planItemStatuses={planItemStatuses}
              />
            ) : null}
            <div ref={bottomRef} />
          </div>
          <div className="chat-composer">
            <Input.TextArea
              value={input}
              autoSize={{ minRows: 1, maxRows: 4 }}
              placeholder="描述你的保险需求，例如：30岁，有医保，预算每年3000元，想配置医疗险和重疾险"
              disabled={sending}
              onChange={(event) => setInput(event.target.value)}
              onPressEnter={(event) => {
                if (!event.shiftKey) {
                  event.preventDefault();
                  void sendMessage();
                }
              }}
            />
            <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={() => void sendMessage()}>
              发送
            </Button>
          </div>
        </section>
      </main>
      <Modal
        open={renamingThread !== null}
        title="重命名会话"
        okText="保存"
        cancelText="取消"
        onOk={() => void renameThread()}
        onCancel={() => {
          setRenamingThread(null);
          setRenameTitle('');
        }}
      >
        <Input
          value={renameTitle}
          maxLength={80}
          placeholder="请输入会话名称"
          onChange={(event) => setRenameTitle(event.target.value)}
          onPressEnter={() => void renameThread()}
        />
      </Modal>
      <Modal
        open={rejectReasonOpen}
        title="取消保存方案"
        okText="提交"
        cancelText="返回"
        okButtonProps={{ disabled: !rejectReason.trim() }}
        onOk={() => {
          setRejectReasonOpen(false);
          void submitDecision('reject', rejectReason);
        }}
        onCancel={() => setRejectReasonOpen(false)}
      >
        <Input.TextArea
          value={rejectReason}
          autoSize={{ minRows: 3, maxRows: 5 }}
          maxLength={200}
          showCount
          placeholder="请填写取消原因，例如：费用太高了，我想换一个预算更低的方案"
          onChange={(event) => setRejectReason(event.target.value)}
        />
      </Modal>
      <Drawer
        open={selectedSource !== null}
        title="条款引用"
        width={680}
        onClose={() => setSelectedSource(null)}
      >
        {selectedSource ? (
          <ClauseSourceDetail
            answerContent={selectedSource.answerContent}
            source={selectedSource.source}
          />
        ) : null}
      </Drawer>
    </div>
  );
}

interface PlanInterruptCardProps {
  interrupt: PlanInterrupt;
  loading: boolean;
  onApprove: () => void;
  onReject: () => void;
  onApplyProduct: (target: ApplyProductTarget) => void;
  planItemStatuses: Record<string, ProductPlanStatus>;
}

function MessageContent({
  message,
  onApplyProduct,
  planItemStatuses,
  onSourceClick,
}: {
  message: ChatMessage;
  onApplyProduct: (target: ApplyProductTarget) => void;
  planItemStatuses: Record<string, ProductPlanStatus>;
  onSourceClick: (source: ClauseSource, answerContent: string) => void;
}) {
  const sources = extractClauseSources(message.additionalInfo);
  const sourceRefs = buildSourceRefs(message.content, sources);
  const sourceById = new Map(sources.map((source) => [source.source_id, source]));
  return (
    <>
      <MarkdownMessage
        content={message.content}
        sourceRefs={sourceRefs.map((item) => ({ sourceId: item.source.source_id, number: item.number }))}
        onSourceClick={(sourceId) => {
          const source = sourceById.get(sourceId);
          if (source) onSourceClick(source, message.content);
        }}
      />
      {sourceRefs.length ? (
        <div className="source-list">
          <strong>引用来源</strong>
          {sourceRefs.map((item) => (
            <button
              key={item.source.source_id}
              type="button"
              onClick={() => onSourceClick(item.source, message.content)}
            >
              <span>[{item.number}]</span>
              <FilePdfOutlined />
              <span>{sourceReferenceLabel(item.source)}</span>
            </button>
          ))}
        </div>
      ) : null}
      <ProductInfoPanel
        info={message.additionalInfo}
        onApplyProduct={onApplyProduct}
        planItemStatuses={planItemStatuses}
      />
      <PolicyInfoPanel info={message.additionalInfo} />
    </>
  );
}

function extractClauseSources(info: AdditionalInfo[] | undefined): ClauseSource[] {
  return (info ?? [])
    .filter((item): item is Extract<AdditionalInfo, { type: 'clause_sources' }> =>
      item.type === 'clause_sources',
    )
    .flatMap((item) => item.sources);
}

function buildSourceRefs(content: string, sources: ClauseSource[]) {
  return sources
    .map((source) => {
      const index = findSourceIndex(content, source.source_id);
      return index >= 0 ? { source, index } : null;
    })
    .filter((item): item is { source: ClauseSource; index: number } => item !== null)
    .sort((left, right) => left.index - right.index)
    .map((item, index) => ({ ...item, number: index + 1 }));
}

function findSourceIndex(content: string, sourceId: string): number {
  const pattern = new RegExp(`\\[?${escapeRegExp(sourceId)}\\]?`);
  return content.search(pattern);
}

function ProductInfoPanel({
  info,
  onApplyProduct,
  planItemStatuses,
}: {
  info: AdditionalInfo[] | undefined;
  onApplyProduct: (target: ApplyProductTarget) => void;
  planItemStatuses: Record<string, ProductPlanStatus>;
}) {
  const groups = (info ?? []).filter((item): item is Extract<AdditionalInfo, { type: 'products' }> =>
    item.type === 'products',
  );
  if (groups.length === 0) return null;
  return (
    <div className="additional-products">
      {groups.map((group, groupIndex) => (
        <section key={`${group.title}-${groupIndex}`}>
          <h4>{group.title}</h4>
          <div className="additional-product-grid">
            {group.products.map((product, index) => (
              <ProductInfoCard
                product={product}
                key={textOf(product.product_id ?? product.id ?? index)}
                onApplyProduct={onApplyProduct}
                planItemStatuses={planItemStatuses}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function ProductInfoCard({
  product,
  onApplyProduct,
  planItemStatuses,
}: {
  product: AdditionalProduct;
  onApplyProduct: (target: ApplyProductTarget) => void;
  planItemStatuses: Record<string, ProductPlanStatus>;
}) {
  const name = textOf(product.name ?? product.product_name ?? '保险产品');
  const premium = product.annual_premium_budget ?? product.min_premium;
  const reason = product.recommendation_reason ?? product.reason;
  const status = productPlanStatus(product.status);
  const productId = productIdOf(product);
  const planId = textOf(product.plan_id).trim() || null;
  const itemId = textOf(product.id).trim() || null;
  const showApplyStatus = hasOwn(product, 'status') && hasOwn(product, 'plan_id') && status !== null;
  const displayStatus = showApplyStatus
    ? itemId ? planItemStatuses[itemId] ?? status : status
    : null;
  return (
    <article className="additional-product-card">
      <ProductInfoImage
        imageUrl={product.image_url}
        name={name}
        category={product.category}
      />
      <div className="additional-product-card__body">
      <div className="additional-product-card__title">
        <strong>{name}</strong>
        {product.category ? <span>{formatCategoryLabel(product.category)}</span> : null}
      </div>
      {product.description ? <p>{textOf(product.description)}</p> : null}
      {reason ? <p>{textOf(reason)}</p> : null}
      {Array.isArray(product.highlights) && product.highlights.length ? (
        <ul>
          {product.highlights.slice(0, 3).map((highlight) => (
            <li key={highlight}>{highlight}</li>
          ))}
        </ul>
      ) : null}
      {premium ? <small>预算参考：¥{textOf(premium)} / 年</small> : null}
        {displayStatus ? (
          <ProductStatusAction
            productId={productId}
            planId={planId}
            itemId={itemId}
            status={displayStatus}
            onApplyProduct={onApplyProduct}
          />
      ) : null}
      </div>
    </article>
  );
}

function ProductInfoImage({
  imageUrl,
  name,
  category,
}: {
  imageUrl?: string | null;
  name: string;
  category?: string;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const fallback = category ? formatCategoryLabel(category) : name.slice(0, 4);
  return (
    <div className="additional-product-card__image">
      {imageUrl && !imageFailed ? (
        <img
          src={imageUrl}
          alt={name}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setImageFailed(true)}
        />
      ) : (
        <span>{fallback}</span>
      )}
    </div>
  );
}

function PolicyInfoPanel({ info }: { info: AdditionalInfo[] | undefined }) {
  const groups = (info ?? []).filter((item): item is Extract<AdditionalInfo, { type: 'policies' }> =>
    item.type === 'policies',
  );
  if (groups.length === 0) return null;
  return (
    <div className="additional-policies">
      {groups.map((group, groupIndex) => (
        <section key={`${group.title}-${groupIndex}`}>
          <h4>{group.title}</h4>
          <div className="policy-card-grid">
            {group.policies.map((policy, index) => (
              <PolicyInfoCard policy={policy} key={textOf(policy.id ?? policy.policy_number ?? index)} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function PolicyInfoCard({ policy }: { policy: AdditionalPolicy }) {
  const productName = textOf(policy.product?.name ?? policy.policy_snapshot?.product_name ?? '保险产品');
  const category = textOf(policy.product?.category ?? policy.policy_snapshot?.category);
  const coverageAmount = policy.coverage_amount ?? policy.coverage_snapshot?.coverage_amount ?? policy.coverage_snapshot?.annual_limit;
  return (
    <article className="policy-card">
      <div className="policy-card__top">
        <div>
          <strong>{productName}</strong>
          {policy.policy_number ? <span>{textOf(policy.policy_number)}</span> : null}
        </div>
        <em className={`policy-status policy-status--${textOf(policy.status || 'active')}`}>
          {formatPolicyStatus(policy.status)}
        </em>
      </div>
      <dl>
        {category ? <PolicyField label="险种" value={formatCategoryLabel(category)} /> : null}
        <PolicyField label="被保人" value={textOf(policy.insured_name || '未提供')} />
        {policy.insured_phone ? <PolicyField label="联系电话" value={textOf(policy.insured_phone)} /> : null}
        <PolicyField label="保障期间" value={policyPeriod(policy)} />
        {coverageAmount ? <PolicyField label="保额/限额" value={`¥${formatMoney(coverageAmount)}`} /> : null}
        {policy.premium_amount ? <PolicyField label="保费" value={`¥${formatMoney(policy.premium_amount)} / 年`} /> : null}
      </dl>
    </article>
  );
}

function PolicyField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function policyPeriod(policy: AdditionalPolicy): string {
  const start = formatDate(policy.effective_at);
  const end = formatDate(policy.expires_at);
  if (start && end) return `${start} 至 ${end}`;
  return start || end || '未提供';
}

function formatDate(value: unknown): string {
  const text = textOf(value);
  return text ? text.slice(0, 10) : '';
}

function formatMoney(value: unknown): string {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toLocaleString('zh-CN') : textOf(value);
}

function formatPolicyStatus(value: unknown): string {
  switch (textOf(value)) {
    case 'active':
      return '生效中';
    case 'pending':
      return '待生效';
    case 'expired':
      return '已失效';
    case 'terminated':
      return '已终止';
    default:
      return textOf(value || '未知');
  }
}

interface SelectedSource {
  source: ClauseSource;
  answerContent: string;
}

function ClauseSourceDetail({
  source,
  answerContent,
}: {
  source: ClauseSource;
  answerContent: string;
}) {
  const highlightedBlocks = buildHighlightedBlocks(answerContent, source);
  return (
    <div className="clause-source-detail">
      <div className="clause-source-header">
        <FilePdfOutlined />
        <div>
          <h3>{documentName(source)}</h3>
          <dl>
            {source.clause_no ? (
              <div>
                <dt>注册号</dt>
                <dd>{source.clause_no}</dd>
              </div>
            ) : null}
            {source.section_path ? (
              <div>
                <dt>章节</dt>
                <dd>
                  <SectionPath value={source.section_path} />
                </dd>
              </div>
            ) : null}
          </dl>
        </div>
      </div>
      {source.content ? (
        <div className="clause-source-content">
          <MarkdownMessage
            content={source.content}
            shouldHighlightBlock={(text) => highlightedBlocks.has(normalizeText(text))}
          />
        </div>
      ) : null}
    </div>
  );
}

function SectionPath({ value }: { value: unknown }) {
  const parts = sectionPathParts(value);
  if (parts.length === 0) return null;
  return (
    <div className="section-path">
      {parts.map((part, index) => (
        <span key={`${part}-${index}`}>{part}</span>
      ))}
    </div>
  );
}

function sourceReferenceLabel(source: ClauseSource): string {
  const registration = source.clause_no ? ` 注册号：${source.clause_no}` : '';
  return `${documentName(source)}${registration}`;
}

function documentName(source: ClauseSource): string {
  return source.clause_name || source.document_name || source.source_id;
}

function sectionPathParts(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => textOf(item).trim()).filter(Boolean);
  }
  return textOf(value)
    .split(/\s*[>/／|]\s*|\s{2,}/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildHighlightedBlocks(answerContent: string, source: ClauseSource): Set<string> {
  const referenceSentence = findReferenceSentence(answerContent, source.source_id);
  const content = source.content ?? '';
  if (!referenceSentence || !content) return new Set();

  const paragraphs = content
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter((item) => item && !item.startsWith('#'));
  const scored = paragraphs
    .map((paragraph) => ({
      paragraph,
      score: textSimilarity(referenceSentence, paragraph),
    }))
    .filter((item) => item.score >= 0.08)
    .sort((left, right) => right.score - left.score)
    .slice(0, 2);
  return new Set(scored.map((item) => normalizeText(item.paragraph)));
}

function findReferenceSentence(content: string, sourceId: string): string | null {
  const normalized = content.replace(/\n+/g, ' ');
  const pattern = new RegExp(`[^。！？.!?]*\\[?${escapeRegExp(sourceId)}\\]?[^。！？.!?]*[。！？.!?]?`);
  const match = normalized.match(pattern);
  return match?.[0]?.replace(new RegExp(`\\[?${escapeRegExp(sourceId)}\\]?`, 'g'), '').trim() || null;
}

function textSimilarity(left: string, right: string): number {
  const leftTokens = significantTokens(left);
  const rightTokens = significantTokens(right);
  if (leftTokens.size === 0 || rightTokens.size === 0) return 0;
  let overlap = 0;
  for (const token of leftTokens) {
    if (rightTokens.has(token)) overlap += 1;
  }
  return overlap / Math.sqrt(leftTokens.size * rightTokens.size);
}

function significantTokens(text: string): Set<string> {
  const normalized = normalizeText(text);
  const tokens = new Set<string>();
  for (const match of normalized.matchAll(/[\u4e00-\u9fa5]{2,}|[a-zA-Z0-9]{2,}/g)) {
    const token = match[0].toLowerCase();
    if (!STOP_WORDS.has(token)) tokens.add(token);
  }
  return tokens;
}

function normalizeText(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

const STOP_WORDS = new Set([
  '保险',
  '条款',
  '产品',
  '可以',
  '如果',
  '以及',
  '或者',
  '这个',
  '该款',
  '相关',
  '责任',
  '保障',
]);

function PlanInterruptCard({
  interrupt,
  loading,
  onApprove,
  onReject,
  onApplyProduct,
  planItemStatuses,
}: PlanInterruptCardProps) {
  const items = extractPlanItems(interrupt.plan);
  const planId = planIdOf(interrupt.plan);
  return (
    <div className="plan-interrupt">
      <div className="plan-interrupt__header">
        <div>
          <span>方案确认</span>
          <h3>{interrupt.confirm_info}</h3>
        </div>
        <SafetyCertificateOutlined />
      </div>
      <PlanSummary plan={interrupt.plan} itemCount={items.length} />
      {items.length ? (
        <div className="plan-items">
          {items.map((item, index) => {
            const status = productPlanStatus(item.status);
            const productId = productIdOf(item);
            const itemPlanId = textOf(item.plan_id).trim() || planId;
            const itemId = textOf(item.id).trim() || null;
            const displayStatus = itemId ? planItemStatuses[itemId] ?? status : status;
            return (
              <div className="plan-item" key={textOf(item.id ?? item.product_id ?? index)}>
              <div className="plan-item__top">
                <strong>{textOf(item.name ?? item.product_name ?? `产品 ${index + 1}`)}</strong>
                <span>{formatCategoryLabel(item.category ?? item.insurance_category)}</span>
              </div>
              {item.annual_premium_budget ? (
                <small>预算参考：¥{textOf(item.annual_premium_budget)} / 年</small>
              ) : null}
              {item.recommendation_reason || item.reason ? (
                <p>{textOf(item.recommendation_reason ?? item.reason)}</p>
              ) : null}
              {displayStatus ? (
                <ProductStatusAction
                  productId={productId}
                  planId={itemPlanId}
                  itemId={itemId}
                  status={displayStatus}
                  onApplyProduct={onApplyProduct}
                />
              ) : null}
              </div>
            );
          })}
        </div>
      ) : (
        <pre>{JSON.stringify(interrupt.plan, null, 2)}</pre>
      )}
      <div className="plan-actions">
        <Button
          type="primary"
          icon={<CheckCircleOutlined />}
          loading={loading}
          disabled={!interrupt.action.includes('approve')}
          onClick={onApprove}
        >
          确认保存方案
        </Button>
        <Button
          danger
          icon={<StopOutlined />}
          disabled={loading || !interrupt.action.includes('reject')}
          onClick={onReject}
        >
          继续调整
        </Button>
      </div>
    </div>
  );
}

type ProductPlanStatus = 'uninsured' | 'applying' | 'insured';

const PRODUCT_STATUS_LABELS: Record<ProductPlanStatus, string> = {
  uninsured: '未投保',
  applying: '投保中',
  insured: '已投保',
};

function productPlanStatus(value: unknown): ProductPlanStatus | null {
  const status = textOf(value).toLowerCase();
  if (status === 'uninsured' || status === 'applying' || status === 'insured') return status;
  return null;
}

function productIdOf(record: Record<string, unknown>): string | null {
  const productId = textOf(record.product_id).trim();
  return productId || null;
}

function planIdOf(plan: unknown): string | null {
  if (!plan || typeof plan !== 'object') return null;
  const planId = textOf((plan as Record<string, unknown>).id).trim();
  return planId || null;
}

function collectPlanIds(messages: ChatMessage[], interrupt: PlanInterrupt | null): string[] {
  const planIds = new Set<string>();
  messages.forEach((message) => {
    (message.additionalInfo ?? []).forEach((info) => {
      if (info.type !== 'products') return;
      info.products.forEach((product) => {
        addPlanId(planIds, product.plan_id);
      });
    });
  });
  if (interrupt) {
    addPlanId(planIds, planIdOf(interrupt.plan));
    extractPlanItems(interrupt.plan).forEach((item) => addPlanId(planIds, item.plan_id));
  }
  return Array.from(planIds).sort();
}

function mergePlanItemStatuses(plans: unknown[]): Record<string, ProductPlanStatus> {
  const statuses: Record<string, ProductPlanStatus> = {};
  plans.forEach((plan) => {
    extractPlanItems(plan).forEach((item) => {
      const itemId = textOf(item.id).trim();
      const status = productPlanStatus(item.status);
      if (itemId && status) statuses[itemId] = status;
    });
  });
  return statuses;
}

function addPlanId(target: Set<string>, value: unknown) {
  const planId = textOf(value).trim();
  if (planId) target.add(planId);
}

function ProductStatusAction({
  productId,
  planId,
  itemId,
  status,
  onApplyProduct,
}: {
  productId: string | null;
  planId: string | null;
  itemId: string | null;
  status: ProductPlanStatus;
  onApplyProduct: (target: ApplyProductTarget) => void;
}) {
  const canApply = status !== 'insured' && productId !== null && planId !== null && itemId !== null;
  return (
    <div className="product-status-row">
      <span className={`product-status product-status--${status}`}>
        {PRODUCT_STATUS_LABELS[status]}
      </span>
      {status === 'insured' ? (
        <span className="product-status-note">已完成投保</span>
      ) : (
        <Button
          size="small"
          type={status === 'uninsured' ? 'primary' : 'default'}
          icon={<ShoppingCartOutlined />}
          disabled={!canApply}
          onClick={() => {
            if (productId && planId && itemId) onApplyProduct({ productId, planId, itemId });
          }}
        >
          {status === 'uninsured' ? '去投保' : '继续投保'}
        </Button>
      )}
    </div>
  );
}

function PlanSummary({ plan, itemCount }: { plan: unknown; itemCount: number }) {
  if (!plan || typeof plan !== 'object') return null;
  const record = plan as Record<string, unknown>;
  const name = record.name ?? record.plan_name ?? record.title;
  const summary = record.summary ?? record.budget_note ?? record.recommendation_reason;
  const budget = record.annual_premium_budget;
  if (!name && !summary && !budget && itemCount === 0) return null;
  return (
    <div className="plan-summary">
      <div>
        {name ? <strong>{textOf(name)}</strong> : null}
        {summary ? <p>{textOf(summary)}</p> : null}
      </div>
      <dl>
        <div>
          <dt>产品数</dt>
          <dd>{itemCount}</dd>
        </div>
        {budget ? (
          <div>
            <dt>预算参考</dt>
            <dd>¥{textOf(budget)} / 年</dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}

function extractPlanItems(plan: unknown): Array<Record<string, unknown>> {
  if (!plan || typeof plan !== 'object') return [];
  const record = plan as Record<string, unknown>;
  const rawItems = record.items ?? record.plan_items ?? record.products;
  return Array.isArray(rawItems)
    ? rawItems.filter((item): item is Record<string, unknown> =>
        Boolean(item) && typeof item === 'object',
      )
    : [];
}

function textOf(value: unknown): string {
  if (value === null || value === undefined) return '';
  return typeof value === 'string' ? value : String(value);
}

function hasOwn(record: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, key);
}

function normalizeHistoryMessages(messages: ChatMessage[]): ChatMessage[] {
  return messages.map((message) => ({
    role: message.role,
    content: message.content,
    additionalInfo: normalizeAdditionalInfo(message.additional_info),
  }));
}

function isUnauthorized(reason: unknown): boolean {
  return reason instanceof ApiError && reason.status === 401;
}

function formatThreadTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (num: number) => String(num).padStart(2, '0');
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
