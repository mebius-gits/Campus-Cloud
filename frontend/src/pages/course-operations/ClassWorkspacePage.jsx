import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import MIcon from "../../components/MIcon";
import AiJudgePanel from "../system/groups/AiJudgePanel";
import ConfigPushPanel from "../teaching/ConfigPushPanel";
import { BatchProvisionService } from "../../services/batchProvision";
import { GroupsService } from "../../services/groups";
import { classCatalog, classStudents, classWeeks } from "./courseOperationsMock";
import { getClassSettings, listCourseTemplates, saveClassSettings } from "./courseOperationsStore";
import styles from "./CourseOperations.module.scss";

const TABS = [
  ["overview", "dashboard", "班級總覽", "確認開課條件"],
  ["students", "groups", "加入學生", "建立上課名單"],
  ["weekly", "calendar_view_week", "每週內容", "任務與教材檔案"],
  ["machines", "account_tree", "課程機器", "套用環境模板"],
  ["progress", "checklist", "學生進度", "完成與教師確認"],
  ["ai", "auto_awesome", "AI 檢查", "機器與上課情況"],
];

function normalizeMembers(members) {
  return members.map((member, index) => ({
    id: member.user_id ?? member.id ?? index, name: member.full_name ?? member.name ?? member.email,
    email: member.email, account: member.account ?? member.email?.split("@")[0] ?? "—", vmid: member.vmid,
    machines: member.vmid ? "1/1" : "0/1", machineStatus: member.vm_status === "running" ? "ready" : "warning", done: false,
  }));
}

function Overview({ classItem, members, template, weeks, onStart, onOpenAi, starting, startMessage, isReal }) {
  const isActive = classItem.status === "active";
  const provisionable = Boolean(template?.nodes?.length) && template.nodes.every((node) => node.sourceTemplateId);
  const canStart = members.length > 0 && provisionable && weeks.length > 0 && isReal;
  const completed = [members.length > 0, weeks.length > 0, provisionable].filter(Boolean).length;
  const next = !members.length ? "先加入學生" : !weeks.length ? "安排每週內容" : !provisionable ? "選擇可建機的課程模板" : "確認並建立固定機器";
  return <div className={styles.stack}>
    <section className={styles.readinessPanel}>
      <div className={styles.readinessLead}><span className={styles.sectionEyebrow}>{isActive ? "CLASS ACTIVE" : "READY TO TEACH"}</span><h2>{isActive ? "班級已進入上課階段" : completed === 3 ? "所有開課條件已完成" : `下一步：${next}`}</h2><p>{isActive ? "固定機器工作已送出。接下來從 AI 檢查查看學生機器與上課情況。" : "只有老師完成並確認全部設定後，系統才會為學生建立固定機器。"}</p></div>
      <div className={styles.readinessScore}><div><strong>{isActive ? "3/3" : `${completed}/3`}</strong><span>開課條件</span></div><div className={styles.readinessBar}><i style={{ width: `${isActive ? 100 : completed / 3 * 100}%` }} /></div></div>
      <div className={styles.readinessRows}>
        <div className={members.length ? styles.readinessDone : styles.readinessTodo}><span><MIcon name={members.length ? "check" : "arrow_forward"} size={16} /></span><div><strong>學生名單</strong><small>{members.length ? `${members.length} 位學生已加入` : "尚未加入學生"}</small></div></div>
        <div className={weeks.length ? styles.readinessDone : styles.readinessTodo}><span><MIcon name={weeks.length ? "check" : "arrow_forward"} size={16} /></span><div><strong>每週上課內容</strong><small>{weeks.length ? `${weeks.length} 週任務已安排` : "尚未設定任務與檔案"}</small></div></div>
        <div className={provisionable ? styles.readinessDone : styles.readinessTodo}><span><MIcon name={provisionable ? "check" : "arrow_forward"} size={16} /></span><div><strong>課程機器</strong><small>{provisionable ? `${template.name} · 共 ${template.nodes.length * members.length} 台` : "尚未選擇可建機模板"}</small></div></div>
      </div>
      <div className={styles.overviewFacts}><div><span>授課期間</span><strong>{classItem.startDate} — {classItem.endDate}</strong></div><div><span>每位學生</span><strong>{template ? `${template.nodes.length} 台固定機器` : "尚未設定"}</strong></div><div><span>建機方式</span><strong>確認後一次建立</strong></div></div>
      {startMessage && <p className={styles.persistentFeedback}><MIcon name="info" size={17} />{startMessage}</p>}
      <div className={styles.primaryActionRow}>{isActive ? <button type="button" className={styles.btnPrimary} onClick={onOpenAi}><MIcon name="auto_awesome" size={17} />查看 AI 檢查</button> : <><span>{canStart ? `將送出 ${template.nodes.length} 個批次工作` : `請先${next}`}</span><button type="button" className={styles.btnPrimary} disabled={!canStart || starting} onClick={onStart}><MIcon name="rocket_launch" size={17} />{starting ? "正在送出建機工作…" : `確認設定並建立 ${template ? template.nodes.length * members.length : 0} 台機器`}</button></>}</div>
    </section>
  </div>;
}

function Students({ classItem, members, setMembers, isReal }) {
  const [emails, setEmails] = useState("");
  const [message, setMessage] = useState("");
  const fileRef = useRef(null);
  async function addStudents(event) {
    event.preventDefault();
    const values = emails.split(/[\n,;]/).map((value) => value.trim()).filter(Boolean);
    if (!values.length) return;
    if (isReal) {
      try { await GroupsService.addMembers(classItem.id, values); const detail = await GroupsService.detail(classItem.id); setMembers(normalizeMembers(detail?.members ?? [])); setMessage("學生已加入既有群組。"); setEmails(""); }
      catch (error) { setMessage(error?.message ?? "加入學生失敗"); }
    } else {
      setMembers((current) => [...current, ...values.map((email, index) => ({ id: `${Date.now()}-${index}`, name: email.split("@")[0], email, account: email.split("@")[0], machines: "0/0", machineStatus: "warning", done: false }))]); setEmails(""); setMessage("已加入預覽名單。");
    }
  }
  async function importCsv() {
    const file = fileRef.current?.files?.[0]; if (!file) return;
    if (!isReal) { setMessage("預覽班級不會上傳 CSV；連結既有群組後會使用現有匯入功能。"); return; }
    try { await GroupsService.importCsv(classItem.id, file); const detail = await GroupsService.detail(classItem.id); setMembers(normalizeMembers(detail?.members ?? [])); setMessage("CSV 匯入完成。"); }
    catch (error) { setMessage(error?.message ?? "CSV 匯入失敗"); }
  }
  return <div className={styles.stack}>
    <section className={styles.card}><div className={styles.cardHeader}><div><h2>加入學生</h2><p>直接沿用既有群組的成員管理與 CSV 匯入，不使用小彈窗。</p></div></div><div className={styles.studentTools}><form onSubmit={addStudents}><label className={styles.field}><span>Email，可用逗號或換行分隔</span><textarea rows={3} value={emails} onChange={(event) => setEmails(event.target.value)} placeholder="student01@example.edu&#10;student02@example.edu" /></label><button type="submit" className={styles.btnPrimary}><MIcon name="person_add" size={16} />加入學生</button></form><div className={styles.csvArea}><label className={styles.field}><span>大量匯入 CSV</span><input ref={fileRef} type="file" accept=".csv,text/csv" /></label><button type="button" className={styles.btnSecondary} onClick={importCsv}><MIcon name="upload" size={16} />開始匯入</button></div></div>{message && <p className={styles.inlineMessage}>{message}</p>}</section>
    <section className={styles.card}><div className={styles.cardHeader}><div><h2>學生名單（{members.length} 人）</h2><p>班級學生可先沿用既有群組來源；多機器固定環境待上課機器模板資料模型完成。</p></div></div><div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>學生</th><th>帳號</th><th>Email</th><th>既有 VM</th><th>狀態</th></tr></thead><tbody>{members.map((member) => <tr key={member.id}><td><strong>{member.name}</strong></td><td>{member.account}</td><td>{member.email}</td><td>{member.vmid ?? "—"}</td><td><span className={`${styles.dot} ${member.machineStatus === "ready" ? styles.dotGood : styles.dotWarn}`} />{member.machineStatus === "ready" ? "運行中" : "尚未就緒"}</td></tr>)}</tbody></table></div>{!members.length && <div className={styles.emptyState}><MIcon name="group_add" size={32} /><p>尚未加入學生。</p></div>}</section>
  </div>;
}

function TemplateAndMachines({ members, templates, templateId, setTemplateId, locked }) {
  const template = templates.find((item) => item.id === templateId);
  const totals = template ? { machines: members.length * template.nodes.length, cpu: members.length * template.nodes.reduce((sum, node) => sum + node.cpu, 0), ram: members.length * template.nodes.reduce((sum, node) => sum + node.memory, 0) } : { machines: 0, cpu: 0, ram: 0 };
  return <div className={styles.stack}>
    <section className={styles.card}><div className={styles.cardHeader}><div><h2>選擇課程機器模板</h2><p>套用老師預先設定的機器組合；任務與進度仍由班級管理。</p></div>{locked && <span className={styles.lockBadge}><MIcon name="lock" size={14} />已啟用，設定已鎖定</span>}</div><div className={styles.templateChoices}>{templates.filter((item) => item.status !== "archived").map((item) => <label key={item.id} className={templateId === item.id ? styles.templateSelected : ""}><input type="radio" name="class-template" disabled={locked} checked={templateId === item.id} onChange={() => setTemplateId(item.id)} /><span><MIcon name="account_tree" size={21} /></span><div><strong>{item.name}</strong><p>{item.description}</p><small>v{item.version} · 每位學生 {item.nodes.length} 台固定機器</small></div></label>)}</div></section>
    {template && <><section className={styles.card}><div className={styles.cardHeader}><div><h2>每位學生的固定機器</h2><p>每個節點都引用現有 PVE 範本；班級啟用時會各送出一個批次工作。</p></div></div><div className={styles.blueprintCanvas}>{template.nodes.map((node, index) => <div className={styles.blueprintItem} key={node.id}><article className={styles.machineBlock}><div className={styles.machineTitle}><span><MIcon name={node.icon} size={20} /></span><div><strong>{node.name}</strong><small>{node.image}</small></div><em>{node.type}</em></div><div className={styles.machineSpecs}><span>{node.cpu} CPU</span><span>{node.memory} GB RAM</span><span>{node.disk} GB Disk</span></div></article>{index < template.nodes.length - 1 && <div className={styles.connection}><span>{node.network}</span><i /><MIcon name="arrow_forward" size={18} /></div>}</div>)}</div></section><div className={styles.metricGrid}><div><span>學生</span><strong>{members.length} 人</strong></div><div><span>機器需求</span><strong>{totals.machines} 台</strong></div><div><span>CPU 需求</span><strong>{totals.cpu} cores</strong></div><div><span>記憶體需求</span><strong>{totals.ram} GB</strong></div></div><section className={styles.confirmBar}><div><MIcon name="calculate" size={20} /><span><strong>建機前估算</strong><small>{members.length ? `回到班級總覽確認後，會建立 ${totals.machines} 台固定機器。` : "請先加入學生，才能計算並建立機器。"}</small></span></div></section></>}
  </div>;
}

function WeeklyContent({ classItem, members, templateId, locked, navigate, weeks, setWeeks }) {
  const [selectedId, setSelectedId] = useState(weeks[0]?.id ?? "");
  const [draft, setDraft] = useState({ title: "", date: classItem.startDate ?? "", target: "全部機器", files: "" });
  const selected = weeks.find((week) => week.id === selectedId);
  function addWeek(event) {
    event.preventDefault();
    if (!draft.title.trim()) return;
    const next = { id: `week-${Date.now()}`, week: weeks.length + 1, title: draft.title.trim(), date: draft.date, status: "draft", target: draft.target.trim() || "全部機器", files: draft.files.split(/[\n,]/).map((item) => item.trim()).filter(Boolean), distributed: "尚未派送" };
    setWeeks((current) => [...current, next]); setSelectedId(next.id); setDraft({ title: "", date: "", target: "全部機器", files: "" });
  }
  return <div className={styles.stack}>
    {!locked && <section className={styles.card}><div className={styles.cardHeader}><div><h2>新增每週上課內容</h2><p>先記錄任務與要派送的檔名；開課後再到派送頁上傳實際檔案。</p></div></div><form className={styles.weekBuilder} onSubmit={addWeek}><label className={styles.field}><span>主題／任務</span><input value={draft.title} onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))} placeholder="例如：Apache 與反向代理" /></label><label className={styles.field}><span>上課日期</span><input type="date" value={draft.date} onChange={(event) => setDraft((current) => ({ ...current, date: event.target.value }))} /></label><label className={styles.field}><span>目標機器</span><input value={draft.target} onChange={(event) => setDraft((current) => ({ ...current, target: event.target.value }))} /></label><label className={`${styles.field} ${styles.fieldFull}`}><span>任務檔案名稱（逗號或換行）</span><textarea rows={2} value={draft.files} onChange={(event) => setDraft((current) => ({ ...current, files: event.target.value }))} placeholder="lab.zip, setup.sh" /></label><button type="submit" className={styles.btnPrimary} disabled={!draft.title.trim()}><MIcon name="add" size={16} />加入第 {weeks.length + 1} 週</button></form></section>}
    <section className={styles.card}><div className={styles.cardHeader}><div><h2>班級每週內容（{weeks.length}）</h2><p>這些任務屬於班級，不會寫回課程機器模板。</p></div></div>{weeks.length ? <div className={styles.weekTimeline}>{weeks.map((week) => <button type="button" key={week.id} className={selectedId === week.id ? styles.weekActive : ""} onClick={() => setSelectedId(week.id)}><b>第 {week.week} 週</b><span>{week.title}</span><small>{week.date || "日期未定"} · {week.target}</small><em>{week.status === "completed" ? "已完成" : week.status === "published" ? "已發布" : "草稿"}</em></button>)}</div> : <div className={styles.emptyState}><MIcon name="calendar_add_on" size={32} /><p>尚未安排每週上課內容。</p></div>}</section>
    {selected && <section className={styles.card}><div className={styles.cardHeader}><div><h2>第 {selected.week} 週：{selected.title}</h2><p>開課後，檔案會派送到學生的固定機器，不會重新建機。</p></div>{!locked && <button type="button" className={styles.iconBtn} aria-label="刪除此週" onClick={() => { setWeeks((current) => current.filter((item) => item.id !== selected.id).map((item, index) => ({ ...item, week: index + 1 }))); setSelectedId(weeks.find((item) => item.id !== selected.id)?.id ?? ""); }}><MIcon name="delete_outline" size={18} /></button>}</div><div className={styles.weekDetail}><div><span>上課日期</span><strong>{selected.date || "日期未定"}</strong></div><div><span>任務檔案</span><strong>{selected.files.length} 個</strong></div><div><span>學生派送</span><strong>{selected.distributed}</strong></div><div><span>目標機器</span><strong>{selected.target}</strong></div></div><div className={styles.fileList}>{selected.files.map((file) => <span key={file}><MIcon name="description" size={15} />{file}</span>)}</div>{locked && <div className={styles.actionFooter}><button type="button" className={styles.btnPrimary} onClick={() => navigate(`/class-management/${classItem.id}/delivery`, { state: { classItem, members, templateId, locked } })}><MIcon name="upload_file" size={16} />上傳並派送檔案</button></div>}</section>}
  </div>;
}

function Delivery({ classItem, members, templateId, locked, isReal, navigate }) {
  return <div className={styles.stack}><button type="button" className={styles.backLink} onClick={() => navigate(`/class-management/${classItem.id}/weekly`, { state: { classItem, members, templateId, locked } })}><MIcon name="arrow_back" size={18} />返回每週任務</button>{isReal ? <div className={styles.embeddedFeature}><div className={styles.embeddedHeading}><MIcon name="upload_file" size={20} /><div><strong>檔案派送</strong><p>沿用現有非同步派送與逐台結果輪詢；正式綁定週次仍待開發。</p></div></div><ConfigPushPanel groupId={classItem.id} /></div> : <section className={styles.card}><div className={styles.emptyState}><MIcon name="upload_file" size={32} /><p>預覽班級沒有真實 VMID，檔案派送待班級資料模型完成。</p><span className={styles.devBadge}>待開發</span></div></section>}</div>;
}

function Progress({ members }) {
  const [week, setWeek] = useState(3);
  const [checks, setChecks] = useState(() => Object.fromEntries(members.map((member, index) => [member.id, index < 2])));
  const done = members.filter((member) => checks[member.id]).length;
  return <div className={styles.stack}>
    <div className={styles.integrationStrip}><MIcon name="verified_user" size={19} /><div><strong>進度全部屬於班級</strong><span>學生任務完成與老師確認分欄顯示；AI 檢查仍保持獨立，不會自動改變進度。</span></div><span className={styles.devBadge}>進度持久化待開發</span></div>
    <section className={styles.card}><div className={styles.cardHeader}><div><h2>第 {week} 週學生進度</h2><p>老師可同時查看學生任務完成情況並做正式確認。</p></div><select className={styles.compactSelect} value={week} onChange={(event) => setWeek(Number(event.target.value))}>{classWeeks.map((item) => <option key={item.id} value={item.week}>第 {item.week} 週 · {item.title}</option>)}</select></div><div className={styles.progressSummary}><strong>{done}/{members.length}</strong><span>位學生已由老師確認</span></div><div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>學生</th><th>任務完成</th><th>固定機器</th><th>老師確認</th><th>正式狀態</th></tr></thead><tbody>{members.map((member, index) => <tr key={member.id}><td><strong>{member.name}</strong><small>{member.email}</small></td><td><strong className={index < 2 ? styles.textSuccess : styles.textMuted}>{index < 2 ? "已完成" : "未完成"}</strong></td><td>{member.vmid ?? "待建立"}</td><td><label className={styles.checkbox}><input type="checkbox" checked={Boolean(checks[member.id])} onChange={() => setChecks((current) => ({ ...current, [member.id]: !current[member.id] }))} /><span /></label></td><td><strong className={checks[member.id] ? styles.textSuccess : styles.textMuted}>{checks[member.id] ? "老師已確認" : "尚未確認"}</strong></td></tr>)}</tbody></table></div><div className={styles.actionFooter}><button type="button" className={styles.btnPrimary} disabled><MIcon name="save" size={16} />儲存第 {week} 週進度（待開發）</button></div></section>
  </div>;
}

function AiCheck({ classItem, members, isReal }) {
  if (isReal) return <div className={styles.embeddedFeature}><div className={styles.embeddedHeading}><MIcon name="auto_awesome" size={20} /><div><strong>現有 AI 教師檢查</strong><p>直接使用原本的評分表、受管收集腳本、核准與指定 VM 執行流程；結果只供老師判斷。</p></div></div><AiJudgePanel groupId={classItem.id} members={members.map((member) => ({ user_id: member.id, full_name: member.name, email: member.email, vmid: member.vmid, vm_status: member.machineStatus === "ready" ? "running" : "stopped" }))} /></div>;
  return <section className={styles.card}><div className={styles.cardHeader}><div><h2>班級 AI 檢查</h2><p>目前預覽班級沒有真實班級 ID 與固定機器，完成班級資料模型後才啟用。</p></div><span className={styles.devBadge}>待開發</span></div><div className={styles.ruleGrid}><div><MIcon name="description" size={20} /><strong>評分表</strong><p>上傳文件並由 AI 解析檢查項目。</p></div><div><MIcon name="terminal" size={20} /><strong>收集腳本</strong><p>產生、審查並核准受管腳本。</p></div><div><MIcon name="play_circle" size={20} /><strong>執行與結果</strong><p>指定學生 VM 執行，回傳 AI 輔助判斷。</p></div></div></section>;
}

export default function ClassWorkspacePage() {
  const { classId, section } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const tab = section ?? "overview";
  const stored = getClassSettings(classId);
  const fallback = { ...(classCatalog.find((item) => item.id === classId) ?? {}), ...(location.state?.classItem ?? {}), ...(stored ?? {}) };
  const initial = Object.keys(fallback).length ? fallback : { id: classId, name: "班級工作區", code: String(classId), term: "", teacher: "", students: 0, templateId: null, status: "planning" };
  const [classItem, setClassItem] = useState(initial);
  const [members, setMembers] = useState(location.state?.members ?? (initial.realGroup ? [] : classStudents));
  const [isReal, setIsReal] = useState(Boolean(initial.realGroup));
  const [templateId, setTemplateIdState] = useState(location.state?.templateId ?? initial.templateId ?? "");
  const [locked, setLocked] = useState(location.state?.locked ?? Boolean(initial.templateId && initial.status === "active"));
  const [weeks, setWeeksState] = useState(initial.weeks ?? (initial.preview || initial.id?.startsWith("class-") ? classWeeks : []));
  const [starting, setStarting] = useState(false);
  const [startMessage, setStartMessage] = useState("");
  const [railCollapsed, setRailCollapsed] = useState(false);
  const templates = useMemo(() => listCourseTemplates(), []);
  useEffect(() => { const shouldLoadGroup = initial.realGroup || (!classId.startsWith("class-") && !classId.startsWith("draft-")); if (!shouldLoadGroup || initial.preview) return; let active = true; GroupsService.detail(classId).then((group) => { if (!active) return; setIsReal(true); setMembers(normalizeMembers(group?.members ?? [])); setClassItem((current) => ({ ...current, name: group.name ?? current.name, students: group.members?.length ?? current.students, realGroup: true })); }).catch(() => {}); return () => { active = false; }; }, [classId, initial.realGroup, initial.preview]);
  const template = templates.find((item) => item.id === templateId);
  function setTemplateId(value) { setTemplateIdState(value); saveClassSettings(classId, { templateId: value, templateVersion: templates.find((item) => item.id === value)?.version }); }
  function setWeeks(updater) { setWeeksState((current) => { const next = typeof updater === "function" ? updater(current) : updater; saveClassSettings(classId, { weeks: next }); return next; }); }
  async function startClass() {
    if (!isReal || !template || !members.length || !weeks.length) return;
    setStarting(true); setStartMessage("");
    try {
      const base = (classItem.code || "course").toLowerCase().replace(/[^a-z0-9-]/g, "-").replace(/^-+|-+$/g, "").slice(0, 34) || "course";
      const jobs = [...(classItem.provisionJobs ?? [])];
      for (const [index, node] of template.nodes.entries()) {
        if (jobs.some((item) => item.nodeId === node.id)) continue;
        const job = await BatchProvisionService.submit(classId, {
          resource_type: String(node.type).toLowerCase() === "lxc" ? "lxc" : "qemu",
          hostname_prefix: `${base}-${index + 1}`.slice(0, 50), vm_template_id: node.sourceTemplateId,
          cores: Number(node.cpu), memory: Number(node.memory) * 1024,
          disk_size: Number(node.disk), rootfs_size: Number(node.disk),
          environment_type: `${classItem.name}｜${node.role || node.name}`,
          expiry_date: classItem.endDate || undefined,
        });
        jobs.push({ id: job.id, nodeId: node.id, nodeName: node.name, status: job.status });
        saveClassSettings(classId, { provisionJobs: jobs });
      }
      const next = { ...classItem, status: "active", templateId, templateVersion: template.version, machinesPerStudent: template.nodes.length, totalMachines: members.length * template.nodes.length, provisionJobs: jobs };
      setClassItem(next); setLocked(true); saveClassSettings(classId, next);
      setStartMessage(`已送出 ${jobs.length} 個批次工作，共 ${members.length * template.nodes.length} 台機器；若需要審核，會進入待核准狀態。`);
    } catch (reason) {
      const completed = getClassSettings(classId)?.provisionJobs?.length ?? 0;
      setClassItem((current) => ({ ...current, provisionJobs: getClassSettings(classId)?.provisionJobs ?? current.provisionJobs }));
      setStartMessage(`已保留 ${completed}/${template.nodes.length} 個建機工作；其餘未送出：${reason?.message ?? "請稍後再試"}。再次確認會從未送出的節點繼續。`);
    }
    finally { setStarting(false); }
  }
  return <div className={styles.page}>
    <button type="button" className={styles.backLink} onClick={() => navigate("/class-management")}><MIcon name="arrow_back" size={18} />返回班級清單</button>
    <div className={styles.workspaceHeader}><div><span className={styles.overline}>CLASS · {classItem.code}</span><div className={styles.titleLine}><h1 className={styles.pageTitle}>{classItem.name}</h1></div><p className={styles.pageSubtitle}>{classItem.teacher} · {classItem.term} · {members.length || classItem.students} 位學生</p></div><div className={styles.headerState}><span className={`${styles.statusBadge} ${styles[`status_${classItem.status}`]}`}>{classItem.status === "active" ? "建機中／上課中" : "備課中"}</span>{isReal && <span className={styles.sourceBadge}><MIcon name="link" size={13} />已連結班級資料</span>}</div></div>
    {tab === "delivery" ? <Delivery classItem={classItem} members={members} templateId={templateId} locked={locked} isReal={isReal} navigate={navigate} /> : <div className={`${styles.workspaceLayout} ${railCollapsed ? styles.workspaceLayoutCollapsed : ""}`}><aside className={`${styles.workflowRail} ${railCollapsed ? styles.workflowRailCollapsed : ""}`}><div className={styles.workflowRailHeader}><div><span>教師工作流程</span><strong>{classItem.status === "active" ? "上課進行中" : `${[members.length > 0, weeks.length > 0, Boolean(template)].filter(Boolean).length}/3 已完成`}</strong></div><button type="button" className={styles.railToggle} onClick={() => setRailCollapsed((current) => !current)} aria-label={railCollapsed ? "展開教師工作流程" : "折疊教師工作流程"} title={railCollapsed ? "展開流程" : "折疊流程"}><MIcon name={railCollapsed ? "chevron_right" : "chevron_left"} size={18} /></button></div><nav className={styles.workspaceTabs}>{TABS.map(([key, icon, label, description]) => { const done = key === "students" ? members.length > 0 : key === "weekly" ? weeks.length > 0 : key === "machines" ? Boolean(template) : false; const unavailable = (key === "progress" || key === "ai") && classItem.status !== "active"; return <button type="button" key={key} disabled={unavailable} title={unavailable ? "確認建機後開放" : railCollapsed ? label : undefined} className={`${tab === key ? styles.workspaceTabActive : ""} ${unavailable ? styles.workspaceTabLocked : ""}`} onClick={() => navigate(key === "overview" ? `/class-management/${classId}` : `/class-management/${classId}/${key}`, { state: { classItem, members, templateId, locked } })}><span className={styles.railIcon}><MIcon name={unavailable ? "lock" : done ? "check" : icon} size={17} /></span><span><strong>{label}</strong><small>{unavailable ? "確認建機後開放" : description}</small></span></button>; })}</nav></aside><main className={styles.workspaceContent}>
      {tab === "overview" && <Overview classItem={classItem} members={members} template={template} weeks={weeks} onStart={startClass} onOpenAi={() => navigate(`/class-management/${classId}/ai`, { state: { classItem, members, templateId, locked } })} starting={starting} startMessage={startMessage} isReal={isReal} />}
      {tab === "students" && <Students classItem={classItem} members={members} setMembers={setMembers} isReal={isReal} />}
      {tab === "machines" && <TemplateAndMachines members={members} templates={templates} templateId={templateId} setTemplateId={setTemplateId} locked={locked} />}
      {tab === "weekly" && <WeeklyContent classItem={classItem} members={members} templateId={templateId} locked={locked} navigate={navigate} weeks={weeks} setWeeks={setWeeks} />}
      {tab === "progress" && <Progress members={members} />}
      {tab === "ai" && <AiCheck classItem={classItem} members={members} isReal={isReal} />}
    </main></div>}
  </div>;
}
