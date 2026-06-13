export const QUICK_START_PRESETS = {
  "postgres-vm": {
    id: "postgres-vm",
    title: "PostgreSQL VM",
    desc: "快速建立教學用 SQL 資料庫虛擬機。",
    icon: "storage",
    accent: "#5471bf",
    resourceType: "vm",
    defaultCores: 2,
    defaultDiskGb: 40,
    defaultEnvironmentType: "PostgreSQL Lab",
    defaultMemoryMb: 4096,
    defaultReason:
      "PostgreSQL 教學 VM，用於 SQL 練習、資料庫設計與課程實作，需要可立即使用的虛擬機環境。",
    defaultUsername: "student",
    osInfo: "Ubuntu 24.04 LTS / PostgreSQL lab",
    preferredVmKeywords: ["ubuntu 24", "ubuntu24", "ubuntu 22", "ubuntu22"],
  },
  "python-vm": {
    id: "python-vm",
    title: "Python VM",
    desc: "快速建立 Python 開發與資料分析虛擬機。",
    icon: "code",
    accent: "#3f8f7b",
    resourceType: "vm",
    defaultCores: 2,
    defaultDiskGb: 30,
    defaultEnvironmentType: "Python Lab",
    defaultMemoryMb: 4096,
    defaultReason:
      "Python 教學 VM，用於程式設計、資料分析與套件安裝練習，需要可立即使用的虛擬機環境。",
    defaultUsername: "student",
    osInfo: "Ubuntu 24.04 LTS / Python lab",
    preferredVmKeywords: ["ubuntu 24", "ubuntu24", "ubuntu 22", "ubuntu22"],
  },
};

function normalizeTemplateName(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

export function getQuickStartPreset(presetId) {
  if (!presetId) return null;
  return QUICK_START_PRESETS[presetId] ?? null;
}

export function listQuickStartPresets() {
  return Object.values(QUICK_START_PRESETS);
}

export function pickQuickStartVmTemplateId(templates, preset) {
  if (!Array.isArray(templates) || templates.length === 0 || !preset) return "";

  for (const keyword of preset.preferredVmKeywords || []) {
    const normalizedKeyword = normalizeTemplateName(keyword);
    const match = templates.find((template) =>
      normalizeTemplateName(template.name).includes(normalizedKeyword),
    );
    if (match) return String(match.vmid);
  }

  const ubuntuTemplate = templates.find((template) =>
    normalizeTemplateName(template.name).includes("ubuntu"),
  );
  if (ubuntuTemplate) return String(ubuntuTemplate.vmid);

  return templates[0]?.vmid ? String(templates[0].vmid) : "";
}
