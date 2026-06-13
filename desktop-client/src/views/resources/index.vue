<script lang="ts" setup>
import Breadcrumb from "@/layout/compoenets/Breadcrumb.vue";
import { useAppStore } from "@/store/app";
import { computed, defineComponent, onMounted } from "vue";
import { useI18n } from "vue-i18n";

defineComponent({ name: "Resources" });

const { t } = useI18n();
const appStore = useAppStore();

const refresh = () => {
  if (appStore.loggedIn) appStore.refreshResources();
};

const runningCount = computed(
  () => appStore.resources.filter(resource => resource.status === "running").length
);

const stoppedCount = computed(
  () => appStore.resources.filter(resource => resource.status === "stopped").length
);

onMounted(() => {
  refresh();
});

const statusTagType = (status: string) => {
  if (status === "running") return "success";
  if (status === "stopped") return "info";
  return "danger";
};
</script>

<template>
  <div class="main">
    <breadcrumb />
    <div class="app-container-breadcrumb">
      <div class="page-surface">
        <div class="page-header">
          <div>
            <div class="page-title">{{ t("resources.title") }}</div>
            <div class="page-subtitle">
              {{ appStore.resources.length }} / {{ runningCount }} / {{ stoppedCount }}
            </div>
          </div>
          <el-button size="small" type="primary" @click="refresh">
            <IconifyIconOffline icon="refresh-rounded" />
            {{ t("resources.refresh") }}
          </el-button>
        </div>

        <div class="metric-grid">
          <div class="metric-item">
            <div class="metric-label">{{ t("resources.title") }}</div>
            <div class="metric-value">{{ appStore.resources.length }}</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">{{ t("home.status.running") }}</div>
            <div class="metric-value metric-value--success">{{ runningCount }}</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">{{ t("home.status.stopped") }}</div>
            <div class="metric-value metric-value--muted">{{ stoppedCount }}</div>
          </div>
        </div>

        <section class="section-panel">
          <div class="section-header">
            <div class="section-title">{{ t("resources.title") }}</div>
          </div>

          <el-table
            v-if="appStore.resources.length"
            :data="appStore.resources"
            size="small"
            stripe
          >
            <el-table-column prop="name" :label="t('resources.table.name')" min-width="170">
              <template #default="{ row }">
                <div class="resource-name">
                  <IconifyIconOffline icon="deployed-code-rounded" />
                  <span>{{ row.name }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="vmid" :label="t('resources.table.vmid')" width="80" />
            <el-table-column prop="type" :label="t('resources.table.type')" width="90" />
            <el-table-column :label="t('resources.table.status')" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTagType(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="node" :label="t('resources.table.node')" width="110" />
            <el-table-column prop="ip_address" :label="t('resources.table.ip')" min-width="150">
              <template #default="{ row }">
                <span class="font-mono">{{ row.ip_address || "-" }}</span>
              </template>
            </el-table-column>
            <el-table-column
              prop="environment_type"
              :label="t('resources.table.environment')"
              width="130"
            />
          </el-table>

          <div v-else class="empty-state">
            <div class="empty-icon">
              <IconifyIconOffline icon="cloud-off-rounded" />
            </div>
            {{ t("resources.empty") }}
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.page-header :deep(.el-button) {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.metric-value--success {
  color: var(--color-success);
}

.metric-value--muted {
  color: var(--color-text-muted);
}

.resource-name {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 8px;
  color: var(--color-text-primary);
  font-weight: 700;
}

.resource-name span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
