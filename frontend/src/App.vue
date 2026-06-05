<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Connection, DataAnalysis, Document, Search } from "@element-plus/icons-vue";
import { getHealth } from "./api/health";

type HealthState = "loading" | "online" | "offline";

const healthState = ref<HealthState>("loading");
const healthMessage = ref("正在检查后端服务");
const checkedAt = ref("");

const healthLabel = computed(() => {
  const labels: Record<HealthState, string> = {
    loading: "检查中",
    online: "运行正常",
    offline: "连接失败",
  };

  return labels[healthState.value];
});

const healthTagType = computed(() => {
  if (healthState.value === "online") return "success";
  if (healthState.value === "offline") return "danger";
  return "warning";
});

async function checkHealth() {
  healthState.value = "loading";
  healthMessage.value = "正在检查后端服务";

  try {
    const result = await getHealth();
    healthState.value = result.status === "ok" ? "online" : "offline";
    healthMessage.value =
      result.status === "ok" ? "API 网关响应正常" : `后端返回状态：${result.status}`;
  } catch {
    healthState.value = "offline";
    healthMessage.value = "无法连接后端，请确认 FastAPI 服务已启动";
  } finally {
    checkedAt.value = new Intl.DateTimeFormat("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date());
  }
}

onMounted(checkHealth);
</script>

<template>
  <el-container class="app-shell">
    <el-aside class="sidebar" width="232px">
      <div class="brand">
        <div class="brand-mark">O</div>
        <div>
          <strong>OpsMind</strong>
          <span>运维知识平台</span>
        </div>
      </div>

      <el-menu class="nav-menu" default-active="overview">
        <el-menu-item index="overview">
          <el-icon><DataAnalysis /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="wiki" disabled>
          <el-icon><Document /></el-icon>
          <span>知识库</span>
        </el-menu-item>
        <el-menu-item index="search" disabled>
          <el-icon><Search /></el-icon>
          <span>智能检索</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">M0 项目骨架</div>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div>
          <p class="eyebrow">OPS KNOWLEDGE CENTER</p>
          <h1>系统工作台</h1>
        </div>
        <el-tag effect="plain" type="info">开发环境</el-tag>
      </el-header>

      <el-main class="content">
        <section class="hero">
          <p class="eyebrow">WELCOME TO OPSMIND</p>
          <h2>让运维知识可检索、可追溯、可复用。</h2>
          <p>
            当前正在搭建系统基础能力。服务状态确认后，将逐步接入 Wiki、智能检索和 AI 问答。
          </p>
        </section>

        <section class="dashboard-grid">
          <el-card class="health-card" shadow="never">
            <template #header>
              <div class="card-header">
                <div class="card-title">
                  <el-icon><Connection /></el-icon>
                  <span>后端健康状态</span>
                </div>
                <el-tag :type="healthTagType" effect="dark">{{ healthLabel }}</el-tag>
              </div>
            </template>

            <div class="health-body">
              <div :class="['status-dot', healthState]" />
              <div>
                <strong>{{ healthMessage }}</strong>
                <p>接口：<code>GET /api/v1/health</code></p>
                <p v-if="checkedAt">最近检查：{{ checkedAt }}</p>
              </div>
            </div>

            <el-button :loading="healthState === 'loading'" type="primary" plain @click="checkHealth">
              重新检查
            </el-button>
          </el-card>

          <el-card class="roadmap-card" shadow="never">
            <template #header>
              <div class="card-title">
                <el-icon><DataAnalysis /></el-icon>
                <span>建设进度</span>
              </div>
            </template>
            <el-steps direction="vertical" :active="1" finish-status="success">
              <el-step title="项目骨架" description="前后端工程与基础服务" />
              <el-step title="用户与权限" description="登录、角色和审计日志" />
              <el-step title="Wiki 与文档" description="知识内容管理" />
            </el-steps>
          </el-card>
        </section>
      </el-main>
    </el-container>
  </el-container>
</template>
