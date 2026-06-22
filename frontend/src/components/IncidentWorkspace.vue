<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Delete, Link, Plus, Refresh, Search } from "@element-plus/icons-vue";
import {
  buildIncidentWikiRelationships,
  createIncident,
  deleteIncident,
  listIncidents,
  publishIncidentToWiki,
  readIncident,
  updateIncident,
  type IncidentCase,
  type IncidentListItem,
  type IncidentPayload,
  type IncidentSeverity,
  type IncidentStatus,
} from "../api/incidents";

const props = defineProps<{ token: string; canDelete: boolean }>();
const emit = defineEmits<{ openWiki: [pageId: number] }>();

const loading = ref(false);
const saving = ref(false);
const publishing = ref(false);
const building = ref(false);
const incidents = ref<IncidentListItem[]>([]);
const selected = ref<IncidentCase | null>(null);

const filters = reactive({ q: "", system_name: "", severity: "", status: "" });
const form = reactive({
  id: 0,
  title: "",
  system_name: "",
  severity: "medium" as IncidentSeverity,
  status: "open" as IncidentStatus,
  symptom: "",
  cause: "",
  investigation_process: "",
  solution: "",
  review_conclusion: "",
  occurred_at: "",
  resolved_at: "",
});

const severityOptions = [
  { label: "低", value: "low" },
  { label: "中", value: "medium" },
  { label: "高", value: "high" },
  { label: "严重", value: "critical" },
];
const statusOptions = [
  { label: "待处理", value: "open" },
  { label: "排查中", value: "investigating" },
  { label: "已解决", value: "resolved" },
  { label: "已关闭", value: "closed" },
];

function severityText(value: string) {
  return severityOptions.find((item) => item.value === value)?.label ?? value;
}

function statusText(value: string) {
  return statusOptions.find((item) => item.value === value)?.label ?? value;
}

function severityTag(value: IncidentSeverity) {
  if (value === "critical") return "danger";
  if (value === "high") return "warning";
  if (value === "low") return "info";
  return "primary";
}

function formatTime(value: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function resetForm() {
  selected.value = null;
  Object.assign(form, {
    id: 0,
    title: "",
    system_name: "",
    severity: "medium",
    status: "open",
    symptom: "",
    cause: "",
    investigation_process: "",
    solution: "",
    review_conclusion: "",
    occurred_at: "",
    resolved_at: "",
  });
}

function fillForm(incident: IncidentCase) {
  selected.value = incident;
  Object.assign(form, {
    ...incident,
    system_name: incident.system_name ?? "",
    cause: incident.cause ?? "",
    investigation_process: incident.investigation_process ?? "",
    solution: incident.solution ?? "",
    review_conclusion: incident.review_conclusion ?? "",
    occurred_at: incident.occurred_at ?? "",
    resolved_at: incident.resolved_at ?? "",
  });
}

async function loadList(selectId?: number) {
  loading.value = true;
  try {
    incidents.value = await listIncidents(props.token, {
      q: filters.q.trim() || undefined,
      system_name: filters.system_name.trim() || undefined,
      severity: (filters.severity || undefined) as IncidentSeverity | undefined,
      status: (filters.status || undefined) as IncidentStatus | undefined,
    });
    const targetId = selectId ?? selected.value?.id;
    if (targetId && incidents.value.some((item) => item.id === targetId)) await selectIncident(targetId);
    else if (incidents.value.length && !form.id) await selectIncident(incidents.value[0].id);
  } catch {
    ElMessage.error("加载故障案例失败");
  } finally {
    loading.value = false;
  }
}

async function selectIncident(id: number) {
  try {
    fillForm(await readIncident(props.token, id));
  } catch {
    ElMessage.error("加载故障详情失败");
  }
}

function nullable(value: string) {
  return value.trim() || null;
}

function payload(): IncidentPayload {
  return {
    title: form.title.trim(),
    system_name: nullable(form.system_name),
    severity: form.severity,
    status: form.status,
    symptom: form.symptom.trim(),
    cause: nullable(form.cause),
    investigation_process: nullable(form.investigation_process),
    solution: nullable(form.solution),
    review_conclusion: nullable(form.review_conclusion),
    occurred_at: form.occurred_at || null,
    resolved_at: form.resolved_at || null,
  };
}

async function save() {
  if (!form.title.trim() || !form.symptom.trim()) {
    ElMessage.warning("请填写标题和故障现象");
    return;
  }
  saving.value = true;
  try {
    const result = form.id
      ? await updateIncident(props.token, form.id, payload())
      : await createIncident(props.token, payload());
    ElMessage.success(form.id ? "故障案例已更新" : "故障案例已创建");
    await loadList(result.id);
  } catch {
    ElMessage.error("保存失败，请检查时间范围和字段内容");
  } finally {
    saving.value = false;
  }
}

async function remove() {
  if (!selected.value) return;
  try {
    await ElMessageBox.confirm("案例将被软删除，关联 Wiki 页面不会删除。", "删除故障案例", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
    await deleteIncident(props.token, selected.value.id);
    resetForm();
    await loadList();
    ElMessage.success("故障案例已删除");
  } catch (error) {
    if (error !== "cancel") ElMessage.error("删除故障案例失败");
  }
}

async function publishWiki() {
  if (!selected.value) return;
  publishing.value = true;
  try {
    const page = await publishIncidentToWiki(props.token, selected.value.id);
    ElMessage.success(`已发布到 Wiki：${page.title}`);
    await loadList(selected.value.id);
  } catch {
    ElMessage.error("发布失败，生成 Slug 可能已被其他页面占用");
  } finally {
    publishing.value = false;
  }
}

async function buildRelationships() {
  if (!selected.value) return;
  building.value = true;
  try {
    const result = await buildIncidentWikiRelationships(props.token, selected.value.id);
    ElMessage.success(
      `关系构建完成：${result.relationship_ids.length} 条关系，${result.created_page_ids.length} 个新页面`,
    );
    await loadList(selected.value.id);
  } catch {
    ElMessage.error("关系构建失败，请先发布到 Wiki 或检查页面冲突");
  } finally {
    building.value = false;
  }
}

onMounted(() => loadList());
</script>

<template>
  <section class="incident-workspace">
    <aside class="incident-list-panel">
      <div class="panel-heading">
        <div>
          <p>INCIDENT CASES</p>
          <strong>故障案例</strong>
        </div>
        <div>
          <el-button :icon="Refresh" circle plain size="small" @click="loadList()" />
          <el-button :icon="Plus" circle size="small" type="primary" @click="resetForm" />
        </div>
      </div>

      <div class="incident-filters">
        <el-input v-model="filters.q" :prefix-icon="Search" clearable placeholder="标题、现象、原因" @keyup.enter="loadList()" />
        <el-input v-model="filters.system_name" clearable placeholder="系统名称" @keyup.enter="loadList()" />
        <el-select v-model="filters.severity" clearable placeholder="严重级别">
          <el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="处理状态">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button type="primary" plain @click="loadList()">筛选</el-button>
      </div>

      <div v-loading="loading" class="incident-list">
        <button
          v-for="incident in incidents"
          :key="incident.id"
          :class="['incident-row', { active: selected?.id === incident.id }]"
          type="button"
          @click="selectIncident(incident.id)"
        >
          <div>
            <el-tag :type="severityTag(incident.severity)" effect="plain" size="small">
              {{ severityText(incident.severity) }}
            </el-tag>
            <span>{{ statusText(incident.status) }}</span>
          </div>
          <strong>{{ incident.title }}</strong>
          <small>{{ incident.system_name || "未指定系统" }} · {{ formatTime(incident.occurred_at) }}</small>
        </button>
        <p v-if="!loading && incidents.length === 0" class="incident-empty">暂无故障案例</p>
      </div>
    </aside>

    <section class="incident-editor-panel">
      <div class="editor-heading">
        <div>
          <p>{{ form.id ? `INCIDENT #${form.id}` : "NEW INCIDENT" }}</p>
          <h2>{{ form.id ? "故障详情与复盘" : "记录故障案例" }}</h2>
        </div>
        <div class="editor-actions">
          <el-button v-if="selected?.wiki_page_id" :icon="Link" plain @click="emit('openWiki', selected.wiki_page_id)">
            查看 Wiki
          </el-button>
          <el-button v-if="form.id" :loading="publishing" plain @click="publishWiki">发布 Wiki</el-button>
          <el-button v-if="form.id" :loading="building" plain @click="buildRelationships">构建关系</el-button>
          <el-button :loading="saving" type="primary" @click="save">保存</el-button>
          <el-button v-if="form.id && canDelete" :icon="Delete" type="danger" plain @click="remove">删除</el-button>
        </div>
      </div>

      <el-alert
        v-if="selected?.wiki_page_id"
        :closable="false"
        show-icon
        title="该案例已关联 Wiki 页面；修改案例后请重新发布，并按需重新构建关系。"
        type="success"
      />

      <el-form class="incident-form" label-position="top">
        <div class="field-grid four-columns">
          <el-form-item class="span-two" label="案例标题">
            <el-input v-model="form.title" maxlength="200" show-word-limit />
          </el-form-item>
          <el-form-item label="相关系统">
            <el-input v-model="form.system_name" maxlength="200" />
          </el-form-item>
          <el-form-item label="严重级别">
            <el-select v-model="form.severity">
              <el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="处理状态">
            <el-select v-model="form.status">
              <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="发生时间">
            <el-date-picker v-model="form.occurred_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" />
          </el-form-item>
          <el-form-item label="解决时间">
            <el-date-picker v-model="form.resolved_at" clearable type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" />
          </el-form-item>
        </div>

        <el-form-item label="故障现象">
          <el-input v-model="form.symptom" :autosize="{ minRows: 3, maxRows: 8 }" type="textarea" />
        </el-form-item>
        <div class="field-grid two-columns">
          <el-form-item label="故障原因">
            <el-input v-model="form.cause" :autosize="{ minRows: 5, maxRows: 12 }" type="textarea" />
          </el-form-item>
          <el-form-item label="排查过程">
            <el-input v-model="form.investigation_process" :autosize="{ minRows: 5, maxRows: 12 }" type="textarea" />
          </el-form-item>
          <el-form-item label="修复方案">
            <el-input v-model="form.solution" :autosize="{ minRows: 5, maxRows: 12 }" type="textarea" />
          </el-form-item>
          <el-form-item label="复盘结论">
            <el-input v-model="form.review_conclusion" :autosize="{ minRows: 5, maxRows: 12 }" type="textarea" />
          </el-form-item>
        </div>
      </el-form>
    </section>
  </section>
</template>

<style scoped>
.incident-workspace { display: grid; grid-template-columns: 330px minmax(0, 1fr); min-height: calc(100vh - 150px); overflow: hidden; border: 1px solid #dfe9eb; border-radius: 10px; background: #fff; }
.incident-list-panel { display: flex; min-height: 0; flex-direction: column; border-right: 1px solid #dfe9eb; background: #f7fafb; }
.panel-heading, .editor-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 20px; border-bottom: 1px solid #e6eef0; }
.panel-heading p, .editor-heading p { margin: 0 0 4px; color: #789098; font-size: 11px; font-weight: 700; letter-spacing: .12em; }
.panel-heading strong { color: #183943; font-size: 18px; }
.incident-filters { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 14px; border-bottom: 1px solid #e6eef0; }
.incident-filters > :first-child, .incident-filters > :nth-child(2), .incident-filters > :last-child { grid-column: 1 / -1; }
.incident-list { display: grid; align-content: start; gap: 8px; min-height: 200px; padding: 12px; overflow-y: auto; }
.incident-row { display: grid; gap: 8px; padding: 13px; text-align: left; border: 1px solid #dfe9eb; border-radius: 8px; background: #fff; cursor: pointer; }
.incident-row:hover, .incident-row.active { border-color: #2f8f8a; box-shadow: 0 5px 14px rgb(34 94 99 / 8%); }
.incident-row.active { background: #f1f9f8; }
.incident-row > div { display: flex; align-items: center; justify-content: space-between; color: #60757d; font-size: 12px; }
.incident-row strong { color: #183943; line-height: 1.45; }
.incident-row small { color: #789098; }
.incident-empty { padding: 30px 0; color: #789098; text-align: center; }
.incident-editor-panel { min-width: 0; overflow-y: auto; }
.editor-heading { position: sticky; z-index: 2; top: 0; background: rgb(255 255 255 / 96%); backdrop-filter: blur(8px); }
.editor-heading h2 { margin: 0; color: #183943; font-size: 21px; }
.editor-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; }
.incident-editor-panel > .el-alert { margin: 18px 22px 0; width: auto; }
.incident-form { padding: 22px; }
.field-grid { display: grid; gap: 0 14px; }
.four-columns { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.two-columns { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.span-two { grid-column: span 2; }
.incident-form :deep(.el-select), .incident-form :deep(.el-date-editor) { width: 100%; }
@media (max-width: 1100px) { .incident-workspace { grid-template-columns: 280px minmax(0, 1fr); } .four-columns { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 820px) { .incident-workspace { grid-template-columns: 1fr; } .incident-list-panel { max-height: 440px; border-right: 0; border-bottom: 1px solid #dfe9eb; } }
@media (max-width: 560px) { .editor-heading { align-items: flex-start; flex-direction: column; } .editor-actions { justify-content: flex-start; } .four-columns, .two-columns { grid-template-columns: 1fr; } .span-two { grid-column: auto; } }
</style>
