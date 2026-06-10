import { useEffect, useMemo, useState } from "react";
import styles from "./RequestReviewPage.module.scss";
import MIcon from "../../../components/MIcon";
import { useToast } from "../../../hooks/useToast";
import { VmRequestsService } from "../../../services/vmRequests";

const TABS = [
  { key: "pending", label: "待審核" },
  { key: "approved", label: "已通過" },
  { key: "rejected", label: "已拒絕" },
  { key: "all", label: "全部" },
];

const STATUS_META = {
  pending: { label: "待審核", tone: "info" },
  approved: { label: "已通過", tone: "success" },
  rejected: { label: "已拒絕", tone: "danger" },
  cancelled: { label: "已取消", tone: "muted" },
};

const EMPTY_TEXT = {
  pending: "目前沒有待審核的申請",
  approved: "目前沒有已通過的申請",
  rejected: "目前沒有已拒絕的申請",
  all: "目前沒有申請紀錄",
};

function formatDateTime(value) {
  if (!value) return "未設定";
  return new Date(value).toLocaleString("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatRange(startAt, endAt) {
  if (!startAt && !endAt) return "未設定";
  if (!endAt) return `${formatDateTime(startAt)} 起`;
  return `${formatDateTime(startAt)} - ${formatDateTime(endAt)}`;
}

function requestTitle(request) {
  return request?.hostname || request?.name || "未命名申請";
}

function requestUser(request) {
  return request?.user_full_name || request?.user_email || "未知使用者";
}

function specLabel(request) {
  if (!request) return "-";
  const disk = request.resource_type === "vm"
    ? `${request.disk_size ?? 0} GB Disk`
    : `${request.rootfs_size ?? 0} GB Rootfs`;
  return `${request.cores} CPU / ${(request.memory / 1024).toFixed(1)} GB RAM / ${disk}`;
}

function StatusBadge({ status }) {
  const meta = STATUS_META[status] ?? { label: status, tone: "muted" };
  return (
    <span className={`${styles.badge} ${styles[`badge_${meta.tone}`]}`}>
      {meta.label}
    </span>
  );
}

function EmptyState({ tab }) {
  return (
    <div className={styles.empty}>
      <div className={styles.emptyIcon}>
        <MIcon name="assignment_turned_in" size={40} />
      </div>
      <h2 className={styles.emptyTitle}>沒有申請</h2>
      <p className={styles.emptyDesc}>{EMPTY_TEXT[tab]}</p>
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className={styles.infoRow}>
      <span>{label}</span>
      <strong>{value || "-"}</strong>
    </div>
  );
}

export default function RequestReviewPage() {
  const toast = useToast();
  const [activeTab, setActiveTab] = useState("pending");
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [context, setContext] = useState(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [contextError, setContextError] = useState("");
  const [comment, setComment] = useState("");
  const [reviewing, setReviewing] = useState(false);

  const selected = useMemo(
    () => requests.find((request) => request.id === selectedId) ?? requests[0] ?? null,
    [requests, selectedId],
  );

  async function fetchRequests(tab = activeTab) {
    setLoading(true);
    setError("");
    try {
      const res = await VmRequestsService.listAll(tab === "all" ? undefined : tab);
      const data = res.data ?? [];
      setRequests(data);
      setSelectedId((current) => (
        current && data.some((item) => item.id === current)
          ? current
          : data[0]?.id ?? null
      ));
    } catch (err) {
      setRequests([]);
      setSelectedId(null);
      setError(err?.message ?? "讀取申請失敗");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchRequests(activeTab);
    setComment("");
  }, [activeTab]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selected?.id) {
      setContext(null);
      setContextError("");
      return;
    }

    let cancelled = false;
    setContextLoading(true);
    setContextError("");
    setContext(null);
    VmRequestsService.getReviewContext(selected.id)
      .then((res) => { if (!cancelled) setContext(res); })
      .catch((err) => {
        if (!cancelled) setContextError(err?.message ?? "讀取審核資訊失敗");
      })
      .finally(() => { if (!cancelled) setContextLoading(false); });
    return () => { cancelled = true; };
  }, [selected?.id]);

  async function submitReview(status) {
    if (!selected?.id || reviewing) return;
    setReviewing(true);
    try {
      await VmRequestsService.review(selected.id, {
        status,
        review_comment: comment.trim() || null,
      });
      toast.success(status === "approved" ? "申請已核准" : "申請已拒絕");
      setComment("");
      await fetchRequests(activeTab);
    } catch (err) {
      toast.error(err?.message ?? "審核失敗");
    } finally {
      setReviewing(false);
    }
  }

  const effectiveRequest = context?.request ?? selected;
  const isPending = effectiveRequest?.status === "pending";

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div className={styles.pageHeading}>
          <h1 className={styles.pageTitle}>申請審核</h1>
          <p className={styles.pageSubtitle}>審核使用者提交的 VM / LXC 預約申請</p>
        </div>
        <div className={styles.tabs}>
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={`${styles.tab} ${activeTab === tab.key ? styles.tabActive : ""}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.content}>
        <div className={styles.reviewGrid}>
          <section className={styles.listPane}>
            {loading ? (
              <div className={styles.stateBox}>讀取申請中...</div>
            ) : error ? (
              <div className={styles.stateBox}>
                <span>{error}</span>
                <button type="button" className={styles.btnSecondary} onClick={() => fetchRequests(activeTab)}>
                  重新整理
                </button>
              </div>
            ) : requests.length === 0 ? (
              <EmptyState tab={activeTab} />
            ) : (
              <div className={styles.list}>
                {requests.map((request) => (
                  <button
                    key={request.id}
                    type="button"
                    className={`${styles.row} ${selected?.id === request.id ? styles.rowActive : ""}`}
                    onClick={() => { setSelectedId(request.id); setComment(""); }}
                  >
                    <div className={styles.rowIcon}>
                      <MIcon name={request.resource_type === "vm" ? "computer" : "terminal"} size={20} />
                    </div>
                    <div className={styles.rowMain}>
                      <span className={styles.rowName}>{requestTitle(request)}</span>
                      <span className={styles.rowMeta}>
                        {requestUser(request)} · {formatRange(request.start_at, request.end_at)}
                      </span>
                    </div>
                    <StatusBadge status={request.status} />
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className={styles.detailPane}>
            {!effectiveRequest ? (
              <div className={styles.stateBox}>請選擇一筆申請</div>
            ) : (
              <>
                <div className={styles.detailHeader}>
                  <div>
                    <h2>{requestTitle(effectiveRequest)}</h2>
                    <p>{requestUser(effectiveRequest)}</p>
                  </div>
                  <StatusBadge status={effectiveRequest.status} />
                </div>

                <div className={styles.infoGrid}>
                  <InfoRow label="類型" value={effectiveRequest.resource_type === "vm" ? "VM" : "LXC"} />
                  <InfoRow label="規格" value={specLabel(effectiveRequest)} />
                  <InfoRow label="時段" value={formatRange(effectiveRequest.start_at, effectiveRequest.end_at)} />
                  <InfoRow label="模板" value={effectiveRequest.template_id ? `Template #${effectiveRequest.template_id}` : effectiveRequest.ostemplate} />
                  <InfoRow label="GPU" value={effectiveRequest.gpu_mapping_id || "未申請"} />
                  <InfoRow label="預測節點" value={context?.projected_node || effectiveRequest.assigned_node || "尚未評估"} />
                </div>

                <div className={styles.reasonBox}>
                  <span>申請原因</span>
                  <p>{effectiveRequest.reason}</p>
                </div>

                {contextLoading && <div className={styles.stateBox}>讀取資源評估中...</div>}
                {contextError && (
                  <div className={`${styles.stateBox} ${styles.stateError}`}>
                    {contextError}
                  </div>
                )}
                {context && (
                  <div className={styles.contextBox}>
                    <div className={styles.contextTitle}>
                      <MIcon name={context.feasible ? "check_circle" : "warning"} size={18} />
                      <span>{context.feasible ? "目前可分配" : "資源可能不足"}</span>
                    </div>
                    <p>{context.summary}</p>
                    {context.warnings?.length > 0 && (
                      <div className={styles.warningList}>
                        {context.warnings.map((warning) => (
                          <span key={warning}>{warning}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <label className={styles.commentField}>
                  <span>審核備註</span>
                  <textarea
                    value={comment}
                    onChange={(event) => setComment(event.target.value)}
                    disabled={!isPending || reviewing}
                    placeholder="可填寫核准原因或退回說明"
                  />
                </label>

                <div className={styles.rowActions}>
                  {isPending ? (
                    <>
                      <button
                        type="button"
                        className={styles.btnApprove}
                        disabled={reviewing || (context && !context.feasible)}
                        onClick={() => submitReview("approved")}
                      >
                        核准
                      </button>
                      <button
                        type="button"
                        className={styles.btnReject}
                        disabled={reviewing}
                        onClick={() => submitReview("rejected")}
                      >
                        拒絕
                      </button>
                    </>
                  ) : (
                    <span className={styles.doneText}>這筆申請已完成審核。</span>
                  )}
                </div>
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
