<script lang="ts" setup>
import Breadcrumb from "@/layout/compoenets/Breadcrumb.vue";
import router from "@/router";
import { useAppStore } from "@/store/app";
import { on, removeRouterListeners, send } from "@/utils/ipcUtils";
import { useDebounceFn } from "@vueuse/core";
import { ElMessage } from "element-plus";
import { computed, defineComponent, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { ipcRouters } from "../../../electron/core/IpcRouter";

defineComponent({ name: "Home" });

const { t } = useI18n();
const appStore = useAppStore();
const loading = ref(false);

const status = computed(() => {
  if (!appStore.tunnelStatus.running) return "stopped";
  if (appStore.tunnelStatus.connectionError) return "error";
  return "running";
});

const uptime = computed(() => {
  now.value;
  if (!appStore.tunnelStatus.running || appStore.tunnelStatus.lastStartTime <= 0) {
    return "";
  }
  const elapsed = Math.floor(
    (Date.now() - appStore.tunnelStatus.lastStartTime) / 1000
  );
  const h = Math.floor(elapsed / 3600);
  const m = Math.floor((elapsed % 3600) / 60);
  const s = elapsed % 60;
  return `${h}h ${m}m ${s}s`;
});

const tunnelCount = computed(() => appStore.tunnelStatus.tunnels.length);
const localPorts = computed(() =>
  appStore.tunnelStatus.tunnels
    .map(tunnel => tunnel.visitor_port)
    .filter(Boolean)
    .join(", ")
);

const now = ref(Date.now());
const tickTimer = ref<number | null>(null);

const handleToggle = useDebounceFn(() => {
  if (!appStore.loggedIn) {
    router.push({ name: "Login" });
    return;
  }
  loading.value = true;
  if (appStore.tunnelStatus.running) {
    send(ipcRouters.TUNNEL.stop);
  } else {
    send(ipcRouters.TUNNEL.start);
  }
}, 300);

const goLogin = () => router.push({ name: "Login" });

watch(
  () => appStore.tunnelStatus.running,
  () => {
    loading.value = false;
  }
);

onMounted(() => {
  on(ipcRouters.TUNNEL.start, () => {
    loading.value = false;
  });
  on(ipcRouters.TUNNEL.stop, () => {
    loading.value = false;
  });
  tickTimer.value = window.setInterval(() => {
    now.value = Date.now();
  }, 1000);
});

onUnmounted(() => {
  removeRouterListeners(ipcRouters.TUNNEL.start);
  removeRouterListeners(ipcRouters.TUNNEL.stop);
  if (tickTimer.value) clearInterval(tickTimer.value);
});

const goResources = () => router.push({ name: "Resources" });
const goLogs = () => router.push({ name: "Logger" });
const copy = async (value: string) => {
  try {
    await navigator.clipboard.writeText(value);
    ElMessage.success(t("common.copied"));
  } catch {
    ElMessage.error("copy failed");
  }
};

const openSsh = (port: number) => {
  send(ipcRouters.SYSTEM.openSsh, { port });
};

const openRdp = (port: number) => {
  send(ipcRouters.SYSTEM.openRdp, { port });
};
</script>

<template>
  <div class="main">
    <breadcrumb />
    <div class="app-container-breadcrumb">
      <div class="page-surface">
        <div class="page-header">
          <div>
            <div class="page-title">SkyLab Connect</div>
            <div class="page-subtitle">
              <template v-if="!appStore.loggedIn">
                {{ t("home.empty.notLoggedIn") }}
              </template>
              <template v-else-if="status === 'running'">
                {{ t("home.status.uptime", { time: uptime }) }}
              </template>
              <template v-else-if="status === 'error'">
                {{ appStore.tunnelStatus.connectionError }}
              </template>
              <template v-else>
                {{ t("home.status.stopped") }}
              </template>
            </div>
          </div>

          <div
            class="status-pill"
            :class="{
              'status-pill--success': status === 'running',
              'status-pill--danger': status === 'error'
            }"
          >
            <span
              class="status-dot"
              :class="{
                'status-dot--success': status === 'running',
                'status-dot--danger': status === 'error',
                'status-dot--muted': status === 'stopped'
              }"
            />
            <span v-if="status === 'running'">{{ t("home.status.running") }}</span>
            <span v-else-if="status === 'error'">{{ t("home.status.error") }}</span>
            <span v-else>{{ t("home.status.stopped") }}</span>
          </div>
        </div>

        <div class="connection-grid">
          <section class="connection-panel section-panel">
            <div class="connection-icon" :class="`connection-icon--${status}`">
              <IconifyIconOffline icon="rocket-launch-rounded" />
            </div>
            <div class="connection-content">
              <div class="section-title">
                <span v-if="status === 'running'">{{ t("home.status.running") }}</span>
                <span v-else-if="status === 'error'">{{ t("home.status.error") }}</span>
                <span v-else>{{ t("home.status.stopped") }}</span>
              </div>
              <div class="connection-meta">
                <template v-if="!appStore.loggedIn">
                  {{ t("home.empty.notLoggedIn") }}
                </template>
                <template v-else-if="status === 'running'">
                  {{ t("home.status.uptime", { time: uptime }) }}
                </template>
                <template v-else-if="status === 'error'">
                  {{ appStore.tunnelStatus.connectionError }}
                </template>
                <template v-else>
                  {{ t("home.tunnels.empty") }}
                </template>
              </div>

              <div class="connection-actions">
                <el-button v-if="!appStore.loggedIn" type="primary" @click="goLogin">
                  <IconifyIconOffline icon="login-rounded" />
                  {{ t("home.empty.goLogin") }}
                </el-button>
                <el-button v-else type="primary" :disabled="loading" @click="handleToggle">
                  <IconifyIconOffline
                    :icon="appStore.tunnelStatus.running ? 'stop-rounded' : 'play-arrow-rounded'"
                  />
                  {{
                    appStore.tunnelStatus.running
                      ? t("home.button.stop")
                      : t("home.button.start")
                  }}
                </el-button>
                <el-button text @click="goLogs">
                  <IconifyIconOffline icon="file-copy-sharp" />
                  {{ t("router.logger.title") }}
                </el-button>
              </div>
            </div>
          </section>

          <div class="metric-grid">
            <div class="metric-item">
              <div class="metric-label">{{ t("home.tunnels.title") }}</div>
              <div class="metric-value">{{ tunnelCount }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">{{ t("resources.table.ip") }}</div>
              <div class="metric-value metric-value--small">
                {{ localPorts || "127.0.0.1" }}
              </div>
            </div>
          </div>
        </div>

        <section class="section-panel">
          <div class="section-header">
            <div class="section-title">{{ t("home.tunnels.title") }}</div>
            <el-button size="small" text @click="goResources">
              <IconifyIconOffline icon="cloud" />
              {{ t("router.resources.title") }}
            </el-button>
          </div>
          <div
            v-if="!appStore.tunnelStatus.tunnels.length"
            class="empty-state"
          >
            <div class="empty-icon">
              <IconifyIconOffline icon="settings-ethernet-rounded" />
            </div>
            <template v-if="!appStore.tunnelStatus.running">
              {{ t("home.tunnels.empty") }}
            </template>
            <template v-else>
              {{ t("home.empty.noTunnels") }}
            </template>
            <div class="mt-2">
              <el-link type="primary" @click="goResources">
                {{ t("home.empty.goResources") }}
              </el-link>
            </div>
          </div>
          <el-table
            v-else
            :data="appStore.tunnelStatus.tunnels"
            size="small"
            stripe
          >
            <el-table-column prop="vm_name" :label="t('resources.table.name')" />
            <el-table-column prop="vmid" :label="t('resources.table.vmid')" width="80" />
            <el-table-column prop="service" label="Service" width="100" />
            <el-table-column label="127.0.0.1:port" width="180">
              <template #default="{ row }">
                <span class="font-mono">127.0.0.1:{{ row.visitor_port }}</span>
                <el-button
                  class="ml-2"
                  size="small"
                  text
                  @click="copy(`127.0.0.1:${row.visitor_port}`)"
                >
                  <IconifyIconOffline icon="content-copy-rounded" />
                  {{ t("common.copy") }}
                </el-button>
              </template>
            </el-table-column>
            <el-table-column :label="t('home.tunnels.action')" width="110">
              <template #default="{ row }">
                <el-button
                  v-if="String(row.service).toLowerCase() === 'ssh'"
                  size="small"
                  type="primary"
                  @click="openSsh(row.visitor_port)"
                >
                  <IconifyIconOffline icon="terminal-rounded" />
                  {{ t("home.tunnels.connectSsh") }}
                </el-button>
                <el-button
                  v-else-if="String(row.service).toLowerCase() === 'rdp'"
                  size="small"
                  type="primary"
                  @click="openRdp(row.visitor_port)"
                >
                  <IconifyIconOffline icon="desktop-windows-rounded" />
                  {{ t("home.tunnels.connectRdp") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.connection-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(240px, 0.8fr);
  gap: 14px;
}

.connection-panel {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 18px;
}

.connection-icon {
  display: flex;
  width: 56px;
  height: 56px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  color: var(--color-status-neutral);
  font-size: 30px;
  background: var(--color-hover);
  border-radius: 8px;
}

.connection-icon--running {
  color: var(--color-success);
  background: color-mix(in srgb, var(--color-success) 12%, transparent);
}

.connection-icon--error {
  color: var(--color-danger);
  background: color-mix(in srgb, var(--color-danger) 12%, transparent);
}

.connection-content {
  min-width: 0;
}

.connection-meta {
  max-width: 560px;
  margin-top: 6px;
  overflow-wrap: anywhere;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.connection-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.connection-actions :deep(.el-button) {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.metric-value--small {
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .connection-grid {
    grid-template-columns: 1fr;
  }
}
</style>
