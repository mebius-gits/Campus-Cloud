import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import MIcon from "../../components/MIcon";
import { GroupsService } from "../../services/groups";
import { classCatalog } from "./courseOperationsMock";
import { getClassSettings, listCourseTemplates } from "./courseOperationsStore";
import styles from "./CourseOperations.module.scss";

function normalizeGroup(group) {
  return {
    id: String(group.id), name: group.name, code: group.code ?? `GROUP-${String(group.id).slice(0, 8).toUpperCase()}`,
    term: group.term ?? "目前學期", teacher: group.owner_name ?? "授課老師", students: group.member_count ?? group.members?.length ?? 0,
    templateId: group.template_id ?? null, templateVersion: group.template_version ?? null, machinesPerStudent: group.machines_per_student ?? 0,
    status: group.class_status ?? "planning", startDate: group.start_date ?? "尚未設定", endDate: group.end_date ?? "尚未設定",
    readyMachines: group.ready_machines ?? 0, totalMachines: group.total_machines ?? 0, realGroup: true,
    ...getClassSettings(String(group.id)), id: String(group.id), students: group.member_count ?? group.members?.length ?? 0,
  };
}

export default function ClassManagementPage() {
  const navigate = useNavigate();
  const [classes, setClasses] = useState(classCatalog);
  const [source, setSource] = useState("loading");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const templates = useMemo(() => listCourseTemplates(), []);
  useEffect(() => { let active = true; GroupsService.list().then((result) => { const rows = result?.data ?? result ?? []; if (!active) return; if (rows.length) { setClasses(rows.map(normalizeGroup)); setSource("groups"); } else setSource("preview"); }).catch(() => active && setSource("preview")); return () => { active = false; }; }, []);
  const rows = useMemo(() => classes.filter((item) => (status === "all" || item.status === status) && `${item.name} ${item.code}`.toLowerCase().includes(query.toLowerCase())), [classes, query, status]);
  return <div className={styles.page}>
    <div className={styles.pageHeader}><div className={styles.pageHeading}><span className={styles.pageKicker}>TEACHER · CLASSES</span><div className={styles.titleLine}><h1 className={styles.pageTitle}>班級</h1></div><p className={styles.pageSubtitle}>先處理尚未就緒的班級。學生、每週內容與課程機器全部完成後，才能確認建機。</p></div><button type="button" className={styles.btnPrimary} onClick={() => navigate("/class-management/new")}><MIcon name="add" size={16} />建立班級</button></div>
    <div className={styles.integrationStrip}><MIcon name="groups" size={19} /><div><strong>{source === "groups" ? "班級與學生資料已連線" : source === "loading" ? "正在讀取班級資料" : "目前顯示示範資料"}</strong><span>新班級會建立對應學生群組，後續可直接串接批次建機、檔案派送與 AI 檢查。</span></div></div>
    <section className={styles.card}>
      <div className={styles.toolbar}><label className={styles.searchInput}><MIcon name="search" size={18} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜尋班級名稱或代碼" /></label><div className={styles.pillTabs}>{[["all", "全部"], ["active", "上課中"], ["planning", "備課中"], ["archived", "已封存"]].map(([key, label]) => <button type="button" key={key} className={status === key ? styles.pillActive : ""} onClick={() => setStatus(key)}>{label}</button>)}</div></div>
      <div className={styles.listSummary}><span>顯示 {rows.length} 個班級</span><span><i />優先處理未完成項目</span></div>
      <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>班級</th><th>學生</th><th>課程機器</th><th>開課準備</th><th>每週內容</th><th>狀態</th><th /></tr></thead><tbody>{rows.map((item) => { const template = templates.find((candidate) => candidate.id === item.templateId); const ready = [item.students > 0, Boolean(template), (item.weeks?.length ?? 0) > 0].filter(Boolean).length; return <tr key={item.id} className={styles.rowLink} onClick={() => navigate(`/class-management/${item.id}`, { state: { classItem: item } })}><td><strong>{item.name}</strong><small>{item.code} · {item.term}</small></td><td><strong>{item.students} 人</strong><small>{item.students ? "名單已加入" : "待加入學生"}</small></td><td>{template ? <><strong>{template.name}</strong><small>v{template.version} · 每人 {template.nodes.length} 台</small></> : <span className={styles.needsSetup}>待選擇</span>}</td><td><div className={styles.readinessInline}><strong>{item.status === "planning" ? `${ready}/3 已完成` : `${item.readyMachines ?? 0}/${item.totalMachines ?? 0} 台就緒`}</strong><i><b style={{ width: `${item.status === "planning" ? ready / 3 * 100 : item.totalMachines ? item.readyMachines / item.totalMachines * 100 : 0}%` }} /></i><small>{item.status === "planning" ? (ready === 3 ? "可確認建機" : "仍有項目待處理") : "固定環境"}</small></div></td><td><strong>{item.weeks?.length ?? 0} 週</strong><small>{item.weeks?.length ? "已有上課內容" : "待安排"}</small></td><td><span className={`${styles.statusBadge} ${styles[`status_${item.status}`]}`}>{item.status === "active" ? "建機中／上課中" : item.status === "planning" ? "備課中" : "已封存"}</span></td><td><button type="button" className={styles.iconBtn} aria-label="開啟班級"><MIcon name="chevron_right" size={19} /></button></td></tr>; })}</tbody></table></div>
    </section>
  </div>;
}
