import { useState } from "react";
import { useNavigate } from "react-router-dom";
import MIcon from "../../components/MIcon";
import { GroupsService } from "../../services/groups";
import { saveClassSettings } from "./courseOperationsStore";
import styles from "./CourseOperations.module.scss";

export default function ClassCreatePage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", code: "", term: "114-1", startDate: "2026-09-01", endDate: "2027-01-31" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  function update(key, value) { setForm((current) => ({ ...current, [key]: value })); }
  async function submit(event) {
    event.preventDefault();
    if (!form.name.trim()) return;
    setSubmitting(true); setError("");
    try {
      const group = await GroupsService.create({ name: form.name.trim(), description: `${form.code || "未設定代碼"}｜${form.term}｜${form.startDate}–${form.endDate}` });
      const classItem = { id: String(group.id), ...form, teacher: "目前老師", students: 0, templateId: null, templateVersion: null, machinesPerStudent: 0, status: "planning", readyMachines: 0, totalMachines: 0, realGroup: true, weeks: [] };
      saveClassSettings(classItem.id, classItem);
      navigate(`/class-management/${classItem.id}/students`, { state: { classItem } });
    } catch (reason) { setError(reason?.message ?? "建立班級失敗，請稍後再試。"); }
    finally { setSubmitting(false); }
  }
  return <div className={styles.page}>
    <button type="button" className={styles.backLink} onClick={() => navigate("/class-management")}><MIcon name="arrow_back" size={18} />返回班級管理</button>
    <div className={styles.pageHeader}><div className={styles.pageHeading}><div className={styles.titleLine}><h1 className={styles.pageTitle}>建立班級</h1></div><p className={styles.pageSubtitle}>先建立班級，再依序加入學生、安排每週內容與選擇課程機器。</p></div></div>
    <form className={styles.fullPageForm} onSubmit={submit}>
      <section className={styles.card}><div className={styles.cardHeader}><div><span className={styles.sectionNo}>1</span><h2>班級基本資料</h2><p>這些資料用於辨識一次實際授課與租借期間。</p></div></div><div className={styles.formGrid}><label className={styles.field}><span>班級名稱</span><input value={form.name} onChange={(event) => update("name", event.target.value)} placeholder="Linux 系統管理｜114-1" autoFocus /></label><label className={styles.field}><span>班級代碼</span><input value={form.code} onChange={(event) => update("code", event.target.value)} placeholder="CS-LINUX-1141" /></label><label className={styles.field}><span>學期</span><input value={form.term} onChange={(event) => update("term", event.target.value)} /></label><span /><label className={styles.field}><span>開始日期</span><input type="date" value={form.startDate} onChange={(event) => update("startDate", event.target.value)} /></label><label className={styles.field}><span>結束日期</span><input type="date" value={form.endDate} onChange={(event) => update("endDate", event.target.value)} /></label></div></section>
      <section className={styles.card}><div className={styles.cardHeader}><div><span className={styles.sectionNo}>2</span><h2>建立後進入班級設計</h2><p>此時仍是「設計中」，不會建立機器或開始課程。</p></div></div><div className={styles.ruleGrid}><div><MIcon name="group_add" size={20} /><strong>加入學生</strong><p>先確認實際上課名單。</p></div><div><MIcon name="account_tree" size={20} /><strong>選擇上課機器模板</strong><p>再估算整班容量與租借需求。</p></div><div><MIcon name="calendar_view_week" size={20} /><strong>安排每週任務</strong><p>全部確認後才啟用班級並開始上課。</p></div></div></section>
      {error && <p className={styles.errorMessage}>{error}</p>}
      <div className={styles.formActions}><button type="button" className={styles.btnSecondary} onClick={() => navigate("/class-management")}>取消</button><button type="submit" className={styles.btnPrimary} disabled={!form.name.trim() || submitting}><MIcon name="arrow_forward" size={16} />{submitting ? "建立中…" : "建立並加入學生"}</button></div>
    </form>
  </div>;
}
