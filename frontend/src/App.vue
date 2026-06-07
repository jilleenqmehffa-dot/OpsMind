<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Connection,
  DataAnalysis,
  Delete,
  Document,
  Edit,
  Lock,
  Plus,
  Refresh,
  Search,
  SwitchButton,
  Upload,
  User,
} from "@element-plus/icons-vue";
import { getCurrentUser, login, type CurrentUser } from "./api/auth";
import { getHealth } from "./api/health";
import {
  createAttachment,
  createCategory,
  createPage,
  createTag,
  deletePage,
  listAttachments,
  listCategories,
  listPages,
  listTags,
  listVersions,
  readPage,
  updatePage,
  type WikiAttachment,
  type WikiCategory,
  type WikiPage,
  type WikiPageListItem,
  type WikiTag,
  type WikiVersion,
} from "./api/wiki";

type HealthState = "loading" | "online" | "offline";
type ViewKey = "overview" | "wiki" | "search";

const tokenStorageKey = "opsmind.access_token";

const healthState = ref<HealthState>("loading");
const healthMessage = ref("正在检查后端服务");
const checkedAt = ref("");
const activeView = ref<ViewKey>("overview");
const authChecking = ref(true);
const loginLoading = ref(false);
const currentUser = ref<CurrentUser | null>(null);
const accessToken = ref(localStorage.getItem(tokenStorageKey) ?? "");

const wikiLoading = ref(false);
const wikiSaving = ref(false);
const selectedPage = ref<WikiPage | null>(null);
const pages = ref<WikiPageListItem[]>([]);
const categories = ref<WikiCategory[]>([]);
const tags = ref<WikiTag[]>([]);
const versions = ref<WikiVersion[]>([]);
const attachments = ref<WikiAttachment[]>([]);

const loginForm = reactive({
  username: "admin",
  password: "",
});

const pageForm = reactive({
  id: 0,
  title: "",
  slug: "",
  content: "",
  status: "draft",
  category_id: null as number | null,
  tag_ids: [] as number[],
});

const categoryForm = reactive({
  name: "",
  slug: "",
});

const tagForm = reactive({
  name: "",
  slug: "",
});

const attachmentForm = reactive({
  filename: "",
  content_type: "text/markdown",
  size_bytes: 1,
  storage_path: "",
});

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

const displayName = computed(() => {
  if (!currentUser.value) return "未登录";
  return currentUser.value.display_name || currentUser.value.username;
});

const userLevel = computed(() => {
  if (!currentUser.value) return "访客";
  return currentUser.value.is_superuser ? "管理员" : "普通用户";
});

const canDeleteWiki = computed(() => Boolean(currentUser.value?.is_superuser));

function statusText(status: string) {
  const labels: Record<string, string> = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
  };
  return labels[status] ?? status;
}

function formatTime(value: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function resetPageForm() {
  pageForm.id = 0;
  pageForm.title = "";
  pageForm.slug = "";
  pageForm.content = "";
  pageForm.status = "draft";
  pageForm.category_id = null;
  pageForm.tag_ids = [];
}

async function checkHealth() {
  healthState.value = "loading";
  healthMessage.value = "正在检查后端服务";

  try {
    const result = await getHealth();
    healthState.value = result.status === "ok" ? "online" : "offline";
    healthMessage.value = result.status === "ok" ? "API 网关响应正常" : `后端返回状态：${result.status}`;
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

async function loadCurrentUser() {
  if (!accessToken.value) {
    currentUser.value = null;
    authChecking.value = false;
    return;
  }

  authChecking.value = true;
  try {
    currentUser.value = await getCurrentUser(accessToken.value);
  } catch {
    localStorage.removeItem(tokenStorageKey);
    accessToken.value = "";
    currentUser.value = null;
  } finally {
    authChecking.value = false;
  }
}

async function submitLogin() {
  if (!loginForm.username.trim() || !loginForm.password) {
    ElMessage.warning("请输入用户名和密码");
    return;
  }

  loginLoading.value = true;
  try {
    const result = await login({
      username: loginForm.username.trim(),
      password: loginForm.password,
    });
    accessToken.value = result.access_token;
    localStorage.setItem(tokenStorageKey, result.access_token);
    await loadCurrentUser();
    ElMessage.success("登录成功");
  } catch {
    ElMessage.error("登录失败，请检查用户名和密码");
  } finally {
    loginLoading.value = false;
  }
}

function logout() {
  localStorage.removeItem(tokenStorageKey);
  accessToken.value = "";
  currentUser.value = null;
  activeView.value = "overview";
  pages.value = [];
  selectedPage.value = null;
  resetPageForm();
}

async function loadWikiData() {
  if (!accessToken.value) return;
  wikiLoading.value = true;
  try {
    const [categoryData, tagData, pageData] = await Promise.all([
      listCategories(accessToken.value),
      listTags(accessToken.value),
      listPages(accessToken.value),
    ]);
    categories.value = categoryData;
    tags.value = tagData;
    pages.value = pageData;
    if (!selectedPage.value && pageData.length > 0) {
      await selectPage(pageData[0].id);
    }
  } catch {
    ElMessage.error("加载 Wiki 数据失败");
  } finally {
    wikiLoading.value = false;
  }
}

async function selectPage(pageId: number) {
  if (!accessToken.value) return;
  wikiLoading.value = true;
  try {
    selectedPage.value = await readPage(accessToken.value, pageId);
    pageForm.id = selectedPage.value.id;
    pageForm.title = selectedPage.value.title;
    pageForm.slug = selectedPage.value.slug;
    pageForm.content = selectedPage.value.content;
    pageForm.status = selectedPage.value.status;
    pageForm.category_id = selectedPage.value.category_id;
    pageForm.tag_ids = [...selectedPage.value.tag_ids];
    versions.value = await listVersions(accessToken.value, pageId);
    attachments.value = await listAttachments(accessToken.value, pageId);
  } catch {
    ElMessage.error("加载 Wiki 页面失败");
  } finally {
    wikiLoading.value = false;
  }
}

async function savePage() {
  if (!accessToken.value) return;
  if (!pageForm.title.trim() || !pageForm.slug.trim() || !pageForm.content.trim()) {
    ElMessage.warning("请填写标题、Slug 和正文");
    return;
  }

  wikiSaving.value = true;
  try {
    const payload = {
      title: pageForm.title.trim(),
      slug: pageForm.slug.trim(),
      content: pageForm.content,
      status: pageForm.status,
      category_id: pageForm.category_id,
      tag_ids: pageForm.tag_ids,
    };
    const page = pageForm.id
      ? await updatePage(accessToken.value, pageForm.id, payload)
      : await createPage(accessToken.value, payload);
    ElMessage.success(pageForm.id ? "Wiki 页面已更新" : "Wiki 页面已创建");
    await loadWikiData();
    await selectPage(page.id);
  } catch {
    ElMessage.error("保存 Wiki 页面失败，请检查 Slug 是否重复");
  } finally {
    wikiSaving.value = false;
  }
}

async function removeSelectedPage() {
  if (!accessToken.value || !selectedPage.value) return;
  try {
    await ElMessageBox.confirm("删除后页面会被软删除，普通用户不可执行该操作。", "删除 Wiki 页面", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
    await deletePage(accessToken.value, selectedPage.value.id);
    ElMessage.success("Wiki 页面已删除");
    selectedPage.value = null;
    resetPageForm();
    await loadWikiData();
  } catch (error) {
    if (error !== "cancel") {
      ElMessage.error("删除失败，请确认当前账号是管理员");
    }
  }
}

async function addCategory() {
  if (!accessToken.value || !categoryForm.name.trim() || !categoryForm.slug.trim()) return;
  try {
    await createCategory(accessToken.value, categoryForm.name.trim(), categoryForm.slug.trim());
    categoryForm.name = "";
    categoryForm.slug = "";
    categories.value = await listCategories(accessToken.value);
    ElMessage.success("分类已创建");
  } catch {
    ElMessage.error("创建分类失败");
  }
}

async function addTag() {
  if (!accessToken.value || !tagForm.name.trim() || !tagForm.slug.trim()) return;
  try {
    await createTag(accessToken.value, tagForm.name.trim(), tagForm.slug.trim());
    tagForm.name = "";
    tagForm.slug = "";
    tags.value = await listTags(accessToken.value);
    ElMessage.success("标签已创建");
  } catch {
    ElMessage.error("创建标签失败");
  }
}

async function addAttachment() {
  if (!accessToken.value || !selectedPage.value) return;
  if (!attachmentForm.filename.trim() || !attachmentForm.storage_path.trim()) {
    ElMessage.warning("请填写附件文件名和存储路径");
    return;
  }

  try {
    await createAttachment(accessToken.value, selectedPage.value.id, {
      filename: attachmentForm.filename.trim(),
      content_type: attachmentForm.content_type,
      size_bytes: Number(attachmentForm.size_bytes),
      storage_path: attachmentForm.storage_path.trim(),
    });
    attachmentForm.filename = "";
    attachmentForm.storage_path = "";
    attachmentForm.size_bytes = 1;
    attachments.value = await listAttachments(accessToken.value, selectedPage.value.id);
    ElMessage.success("附件元数据已记录");
  } catch {
    ElMessage.error("附件元数据保存失败，请确认类型和大小");
  }
}

async function selectView(view: ViewKey) {
  if (!currentUser.value) {
    activeView.value = "overview";
    ElMessage.warning("请先登录");
    return;
  }

  activeView.value = view;
  if (view === "wiki") {
    await loadWikiData();
  }
}

function handleMenuSelect(key: string) {
  selectView(key as ViewKey);
}

onMounted(() => {
  checkHealth();
  loadCurrentUser();
});
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

      <el-menu class="nav-menu" :default-active="activeView" @select="handleMenuSelect">
        <el-menu-item index="overview">
          <el-icon><DataAnalysis /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="wiki" :disabled="!currentUser">
          <el-icon><Document /></el-icon>
          <span>知识库</span>
        </el-menu-item>
        <el-menu-item index="search" :disabled="!currentUser">
          <el-icon><Search /></el-icon>
          <span>智能检索</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">M2 Wiki 与文档</div>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div>
          <p class="eyebrow">OPS KNOWLEDGE CENTER</p>
          <h1>{{ activeView === "wiki" ? "Wiki 与文档管理" : currentUser ? "系统工作台" : "登录 OpsMind" }}</h1>
        </div>
        <div class="topbar-actions">
          <el-tag effect="plain" type="info">本地开发</el-tag>
          <el-button v-if="currentUser" :icon="SwitchButton" plain @click="logout">退出</el-button>
        </div>
      </el-header>

      <el-main class="content">
        <section v-if="!currentUser" class="auth-layout">
          <div class="auth-copy">
            <p class="eyebrow">AUTHENTICATION</p>
            <h2>先完成身份校验，再进入知识工作台。</h2>
            <p>登录成功后，前端会保存本地访问令牌，并使用该令牌访问受保护的 Wiki 接口。</p>
          </div>

          <el-card class="login-card" shadow="never">
            <template #header>
              <div class="card-title">
                <el-icon><Lock /></el-icon>
                <span>账号登录</span>
              </div>
            </template>

            <el-form class="login-form" label-position="top" @submit.prevent="submitLogin">
              <el-form-item label="用户名">
                <el-input v-model="loginForm.username" autocomplete="username" />
              </el-form-item>
              <el-form-item label="密码">
                <el-input
                  v-model="loginForm.password"
                  autocomplete="current-password"
                  show-password
                  type="password"
                  @keyup.enter="submitLogin"
                />
              </el-form-item>
              <el-button class="login-button" :loading="loginLoading || authChecking" type="primary" @click="submitLogin">
                登录
              </el-button>
            </el-form>
          </el-card>
        </section>

        <template v-else>
          <section v-if="activeView === 'overview'" class="dashboard-grid">
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

            <el-card class="profile-card" shadow="never">
              <template #header>
                <div class="card-title">
                  <el-icon><User /></el-icon>
                  <span>当前身份</span>
                </div>
              </template>

              <div class="profile-row">
                <span>用户</span>
                <strong>{{ displayName }}</strong>
              </div>
              <div class="profile-row">
                <span>权限级别</span>
                <el-tag :type="currentUser.is_superuser ? 'success' : 'info'">{{ userLevel }}</el-tag>
              </div>
              <div class="profile-row">
                <span>账号状态</span>
                <el-tag :type="currentUser.is_active ? 'success' : 'danger'">
                  {{ currentUser.is_active ? "启用" : "停用" }}
                </el-tag>
              </div>
            </el-card>

            <el-card class="roadmap-card" shadow="never">
              <template #header>
                <div class="card-title">
                  <el-icon><DataAnalysis /></el-icon>
                  <span>建设进度</span>
                </div>
              </template>
              <el-steps direction="vertical" :active="3" finish-status="success">
                <el-step title="项目骨架" description="前后端工程与基础服务" />
                <el-step title="用户与权限" description="登录、身份状态和接口保护" />
                <el-step title="Wiki 与文档" description="页面、版本和附件元数据" />
              </el-steps>
            </el-card>
          </section>

          <section v-else-if="activeView === 'wiki'" class="wiki-workspace">
            <aside class="wiki-list">
              <div class="panel-title">
                <span>页面</span>
                <div>
                  <el-button :icon="Refresh" plain size="small" @click="loadWikiData" />
                  <el-button :icon="Plus" size="small" type="primary" @click="resetPageForm" />
                </div>
              </div>

              <div v-loading="wikiLoading" class="page-list">
                <button
                  v-for="page in pages"
                  :key="page.id"
                  :class="['page-row', { active: selectedPage?.id === page.id }]"
                  type="button"
                  @click="selectPage(page.id)"
                >
                  <strong>{{ page.title }}</strong>
                  <span>{{ statusText(page.status) }} · {{ formatTime(page.updated_at) }}</span>
                </button>
                <p v-if="pages.length === 0" class="empty-text">暂无 Wiki 页面</p>
              </div>

              <div class="quick-create">
                <strong>分类</strong>
                <el-input v-model="categoryForm.name" placeholder="名称" size="small" />
                <el-input v-model="categoryForm.slug" placeholder="slug" size="small" />
                <el-button size="small" plain @click="addCategory">添加分类</el-button>
              </div>

              <div class="quick-create">
                <strong>标签</strong>
                <el-input v-model="tagForm.name" placeholder="名称" size="small" />
                <el-input v-model="tagForm.slug" placeholder="slug" size="small" />
                <el-button size="small" plain @click="addTag">添加标签</el-button>
              </div>
            </aside>

            <section class="wiki-editor">
              <div class="editor-toolbar">
                <div class="card-title">
                  <el-icon><Edit /></el-icon>
                  <span>{{ pageForm.id ? "编辑页面" : "创建页面" }}</span>
                </div>
                <div>
                  <el-button :loading="wikiSaving" type="primary" @click="savePage">保存</el-button>
                  <el-button v-if="pageForm.id && canDeleteWiki" :icon="Delete" type="danger" plain @click="removeSelectedPage">
                    删除
                  </el-button>
                </div>
              </div>

              <el-form class="wiki-form" label-position="top">
                <div class="wiki-form-grid">
                  <el-form-item label="标题">
                    <el-input v-model="pageForm.title" />
                  </el-form-item>
                  <el-form-item label="Slug">
                    <el-input v-model="pageForm.slug" />
                  </el-form-item>
                  <el-form-item label="状态">
                    <el-select v-model="pageForm.status">
                      <el-option label="草稿" value="draft" />
                      <el-option label="已发布" value="published" />
                      <el-option label="已归档" value="archived" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="分类">
                    <el-select v-model="pageForm.category_id" clearable>
                      <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
                    </el-select>
                  </el-form-item>
                </div>

                <el-form-item label="标签">
                  <el-select v-model="pageForm.tag_ids" multiple>
                    <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
                  </el-select>
                </el-form-item>

                <el-form-item label="正文">
                  <el-input v-model="pageForm.content" :autosize="{ minRows: 12, maxRows: 22 }" type="textarea" />
                </el-form-item>
              </el-form>

              <div v-if="selectedPage" class="wiki-side-panels">
                <el-card shadow="never">
                  <template #header>
                    <div class="card-title">
                      <el-icon><DataAnalysis /></el-icon>
                      <span>版本记录</span>
                    </div>
                  </template>
                  <div class="compact-list">
                    <div v-for="version in versions" :key="version.id" class="compact-row">
                      <strong>v{{ version.version_number }}</strong>
                      <span>{{ formatTime(version.created_at) }}</span>
                    </div>
                  </div>
                </el-card>

                <el-card shadow="never">
                  <template #header>
                    <div class="card-title">
                      <el-icon><Upload /></el-icon>
                      <span>附件元数据</span>
                    </div>
                  </template>
                  <div class="attachment-form">
                    <el-input v-model="attachmentForm.filename" placeholder="backup.md" size="small" />
                    <el-select v-model="attachmentForm.content_type" size="small">
                      <el-option label="Markdown" value="text/markdown" />
                      <el-option label="TXT" value="text/plain" />
                      <el-option label="PDF" value="application/pdf" />
                      <el-option label="DOCX" value="application/vnd.openxmlformats-officedocument.wordprocessingml.document" />
                    </el-select>
                    <el-input-number v-model="attachmentForm.size_bytes" :min="1" :max="20971520" size="small" />
                    <el-input v-model="attachmentForm.storage_path" placeholder="local/wiki/1/backup.md" size="small" />
                    <el-button size="small" plain @click="addAttachment">记录附件</el-button>
                  </div>
                  <div class="compact-list">
                    <div v-for="attachment in attachments" :key="attachment.id" class="compact-row">
                      <strong>{{ attachment.filename }}</strong>
                      <span>{{ attachment.size_bytes }} bytes</span>
                    </div>
                  </div>
                </el-card>
              </div>
            </section>
          </section>

          <section v-else class="placeholder-panel">
            <el-icon><Lock /></el-icon>
            <h3>智能检索页面待接入</h3>
            <p>Wiki 内容稳定后，再进入索引和检索模块。</p>
          </section>
        </template>
      </el-main>
    </el-container>
  </el-container>
</template>
