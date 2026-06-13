<script lang="ts" setup>
import router from "@/router";
import { useAppStore } from "@/store/app";
import { on, removeRouterListeners, send } from "@/utils/ipcUtils";
import { ElMessage } from "element-plus";
import { ipcRenderer } from "electron";
import { defineComponent, onMounted, onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { ipcRouters } from "../../../electron/core/IpcRouter";

defineComponent({ name: "Login" });

const { t } = useI18n();
const appStore = useAppStore();
const waiting = ref(false);

const handleLogin = () => {
  waiting.value = true;
  send(ipcRouters.AUTH.startLogin);
};

const handleCancel = () => {
  send(ipcRouters.AUTH.logout);
  waiting.value = false;
};

const authEventHandler = (_event: any, args: ApiResponse<any>) => {
  if (!args || args.bizCode !== "A1000") return;
  const payload = args.data;
  if (!payload) return;
  waiting.value = false;
  if (payload.type === "login-success") {
    ElMessage.success(t("login.success"));
    appStore.loggedIn = true;
    appStore.refreshAuth();
    router.replace({ name: "Home" });
  } else if (payload.type === "login-failure") {
    ElMessage.error(
      t("login.failure", { error: payload.error || "unknown" })
    );
  }
};

onMounted(() => {
  on(ipcRouters.AUTH.startLogin, () => {
    waiting.value = true;
  });
  ipcRenderer.on("auth:event", authEventHandler);
});

onUnmounted(() => {
  removeRouterListeners(ipcRouters.AUTH.startLogin);
  ipcRenderer.removeListener("auth:event", authEventHandler);
});
</script>

<template>
  <div class="login-page">
    <div class="login-panel">
      <img src="/logo/only/128x128.png" class="login-logo" alt="Logo" />
      <h1 class="login-title">{{ t("login.title") }}</h1>
      <p class="login-description">
        {{ t("login.description") }}
      </p>
      <el-button
        v-if="!waiting"
        type="primary"
        size="large"
        class="w-full"
        @click="handleLogin"
      >
        {{ t("login.startButton") }}
      </el-button>
      <template v-else>
        <el-button size="large" class="mb-2 w-full" loading>
          {{ t("login.waiting") }}
        </el-button>
        <el-button size="small" text @click="handleCancel">
          {{ t("login.cancelButton") }}
        </el-button>
      </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.login-page {
  position: relative;
  z-index: 1;
  display: flex;
  width: 100%;
  height: 100vh;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.login-panel {
  display: flex;
  width: min(100%, 400px);
  flex-direction: column;
  align-items: center;
  padding: 32px;
  text-align: center;
  background: var(--color-surface-glass);
  border: 1px solid var(--color-surface-glass-border);
  border-radius: 8px;
  box-shadow: var(--shadow-glass);
  backdrop-filter: blur(16px) saturate(1.25);
}

.login-logo {
  width: 72px;
  height: 72px;
  margin-bottom: 18px;
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
}

.login-title {
  margin-bottom: 8px;
  color: var(--color-text-primary);
  font-size: 24px;
  font-weight: 700;
}

.login-description {
  margin-bottom: 24px;
  color: var(--color-text-secondary);
  font-size: 14px;
}
</style>
