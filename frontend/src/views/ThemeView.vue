<template>
  <el-card>
    <template #header>
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <span>主题</span>
        <div style="display:flex;gap:8px">
          <el-button @click="openSlotConfig">配置</el-button>
          <el-button type="success" @click="openCreate">新增</el-button>
        </div>
      </div>
    </template>
    <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
      <el-input
        v-model="keyword"
        placeholder="输入名称、时代背景或描述"
        clearable
        style="width:300px"
        @keyup.enter="runSearch"
      />
      <el-button type="primary" @click="runSearch">查询</el-button>
    </div>

    <el-table :data="filteredRows">
      <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
      <el-table-column prop="historical_background" label="时代背景" min-width="180" show-overflow-tooltip />
      <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="scope">
          <el-button link type="primary" @click="openEdit(scope.row)">编辑</el-button>
          <el-button link type="danger" @click="removeRow(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="open" :title="isEdit ? '编辑' : '新增'" width="560px" destroy-on-close @closed="onDialogClosed">
    <el-form :model="form" label-position="top">
      <el-form-item label="名称" required>
        <el-input v-model="form.name" placeholder="请输入名称" maxlength="120" show-word-limit />
      </el-form-item>
      <el-form-item label="背景设定">
        <div class="theme-field-row">
          <el-input v-model="form.historical_background" placeholder="请输入背景设定" />
          <el-button type="success" :loading="loadingRandomBg" @click="fillRandomBackground">
            <el-icon class="theme-btn-icon"><Refresh /></el-icon>
            随机生成
          </el-button>
        </div>
      </el-form-item>
      <el-form-item label="背景描述">
        <div class="theme-field-row theme-field-row--top">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="5"
            placeholder="请输入描述内容"
          />
          <el-button type="success" class="theme-random-side" :loading="loadingRandomDesc" @click="fillRandomDescription">
            <el-icon class="theme-btn-icon"><Refresh /></el-icon>
            随机生成
          </el-button>
        </div>
      </el-form-item>
      <el-form-item label="AI">
        <div class="theme-field-row">
          <el-input
            v-model="aiHint"
            placeholder="请输入内容，使用ai辅助生成"
            @keyup.enter="submitAi"
          />
          <el-button class="theme-ai-submit" :loading="loadingAi" @click="submitAi">
            <el-icon class="theme-btn-icon"><Promotion /></el-icon>
            提交
          </el-button>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="open = false">取消</el-button>
      <el-button type="success" :loading="saving" @click="save">确认</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="configOpen" title="主题 AI 配置" width="720px" destroy-on-close>
    <el-table :data="slotDefs" border style="width:100%">
      <el-table-column prop="label" label="名称" width="100" />
      <el-table-column label="模型">
        <template #default="{ row }">
          <el-select
            v-model="configDraft[row.key].modelId"
            clearable
            filterable
            placeholder="不选则用已启用的模型"
            style="width:100%"
          >
            <el-option v-for="m in llmOptions" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="提示词">
        <template #default="{ row }">
          <el-select
            v-model="configDraft[row.key].promptId"
            clearable
            filterable
            placeholder="不选则用内置默认"
            style="width:100%"
          >
            <el-option v-for="p in promptOptions" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </template>
      </el-table-column>
    </el-table>
    <p class="theme-config-hint">分别为「背景」「描述」随机生成与「提交」整表 AI 辅助指定模型与提示词模板；提示词内容作为系统指令叠加在默认任务说明上。</p>
    <template #footer>
      <el-button @click="configOpen = false">取消</el-button>
      <el-button type="primary" @click="saveSlotConfig">确认</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Promotion, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'

const THEME_AI_STORAGE_KEY = 'aidirector_theme_ai_slots_v1'

const slotDefs = [
  { key: 'historical_background', label: '背景' },
  { key: 'description', label: '描述' },
  { key: 'ai_submit', label: '提交' },
]

const emptySlot = () => ({
  historical_background: { modelId: null, promptId: null },
  description: { modelId: null, promptId: null },
  ai_submit: { modelId: null, promptId: null },
})

const slotConfig = reactive(emptySlot())
const configDraft = reactive(emptySlot())
const configOpen = ref(false)
const llmOptions = ref([])
const promptOptions = ref([])

const rows = ref([])
const filteredRows = ref([])
const open = ref(false)
const isEdit = ref(false)
const editingId = ref(null)
const form = reactive({
  name: '',
  historical_background: '',
  description: '',
})
const aiHint = ref('')
const keyword = ref('')
const saving = ref(false)
const loadingRandomBg = ref(false)
const loadingRandomDesc = ref(false)
const loadingAi = ref(false)

const normalizedKeyword = computed(() => keyword.value.trim().toLowerCase())

const loadSlotConfigFromStorage = () => {
  try {
    const raw = localStorage.getItem(THEME_AI_STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    for (const { key } of slotDefs) {
      const s = parsed[key]
      if (s && typeof s === 'object') {
        slotConfig[key].modelId = s.modelId ?? null
        slotConfig[key].promptId = s.promptId ?? null
      }
    }
  } catch {
    // ignore
  }
}

const syncDraftFromSlot = () => {
  for (const { key } of slotDefs) {
    configDraft[key].modelId = slotConfig[key].modelId
    configDraft[key].promptId = slotConfig[key].promptId
  }
}

const fetchConfigOptions = async () => {
  const [llmRes, promptRes] = await Promise.all([http.get('/llm/models'), http.get('/prompts')])
  llmOptions.value = llmRes.data || []
  promptOptions.value = promptRes.data || []
}

const openSlotConfig = async () => {
  await fetchConfigOptions()
  syncDraftFromSlot()
  configOpen.value = true
}

const saveSlotConfig = () => {
  for (const { key } of slotDefs) {
    slotConfig[key].modelId = configDraft[key].modelId
    slotConfig[key].promptId = configDraft[key].promptId
  }
  localStorage.setItem(
    THEME_AI_STORAGE_KEY,
    JSON.stringify({
      historical_background: { ...slotConfig.historical_background },
      description: { ...slotConfig.description },
      ai_submit: { ...slotConfig.ai_submit },
    }),
  )
  configOpen.value = false
  ElMessage.success('配置已保存')
}

const fieldAiPayload = (field) => ({
  field,
  model_id: slotConfig[field].modelId,
  prompt_template_id: slotConfig[field].promptId,
  theme_name: form.name || '',
  historical_background: form.historical_background || '',
  description: form.description || '',
  extra_hint: '',
})

const load = async () => {
  const { data } = await http.get('/themes')
  rows.value = data
  runSearch()
}

const runSearch = () => {
  const key = normalizedKeyword.value
  filteredRows.value = rows.value.filter((row) => {
    if (!key) return true
    const name = String(row.name || '').toLowerCase()
    const bg = String(row.historical_background || '').toLowerCase()
    const desc = String(row.description || '').toLowerCase()
    return name.includes(key) || bg.includes(key) || desc.includes(key)
  })
}

const resetForm = () => {
  isEdit.value = false
  editingId.value = null
  form.name = ''
  form.historical_background = ''
  form.description = ''
  aiHint.value = ''
}

const onDialogClosed = () => {
  resetForm()
}

const openCreate = () => {
  resetForm()
  open.value = true
}

const openEdit = (row) => {
  isEdit.value = true
  editingId.value = row.id
  form.name = row.name
  form.historical_background = row.historical_background || ''
  form.description = row.description || ''
  aiHint.value = ''
  open.value = true
}

const fillRandomBackground = async () => {
  loadingRandomBg.value = true
  try {
    try {
      const { data } = await http.post('/themes/ai-field', fieldAiPayload('historical_background'))
      if (data.value) {
        form.historical_background = data.value
        return
      }
    } catch (e) {
      const msg = e.response?.data?.detail || ''
      const { data } = await http.get('/themes/random-historical-background')
      form.historical_background = data.value || ''
      ElMessage.warning(typeof msg === 'string' && msg ? `AI 未可用：${msg}，已使用本地随机示例` : 'AI 生成失败，已使用本地随机示例')
      return
    }
    const { data } = await http.get('/themes/random-historical-background')
    form.historical_background = data.value || ''
  } finally {
    loadingRandomBg.value = false
  }
}

const fillRandomDescription = async () => {
  loadingRandomDesc.value = true
  try {
    try {
      const { data } = await http.post('/themes/ai-field', fieldAiPayload('description'))
      if (data.value) {
        form.description = data.value
        return
      }
    } catch (e) {
      const msg = e.response?.data?.detail || ''
      const { data } = await http.get('/themes/random-description')
      form.description = data.value || ''
      ElMessage.warning(typeof msg === 'string' && msg ? `AI 未可用：${msg}，已使用本地随机示例` : 'AI 生成失败，已使用本地随机示例')
      return
    }
    const { data } = await http.get('/themes/random-description')
    form.description = data.value || ''
  } finally {
    loadingRandomDesc.value = false
  }
}

const submitAi = async () => {
  const hint = aiHint.value.trim()
  if (!hint) {
    ElMessage.warning('请先输入 AI 辅助说明')
    return
  }
  loadingAi.value = true
  try {
    const { data } = await http.post('/themes/ai-assist', {
      hint,
      model_id: slotConfig.ai_submit.modelId,
      prompt_template_id: slotConfig.ai_submit.promptId,
    })
    if (data.name) form.name = data.name
    if (data.historical_background) form.historical_background = data.historical_background
    if (data.description) form.description = data.description
    ElMessage.success('已根据 AI 结果填充表单（可继续修改后确认）')
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '请求失败'
    ElMessage.error(typeof msg === 'string' ? msg : 'AI 辅助失败')
  } finally {
    loadingAi.value = false
  }
}

const save = async () => {
  if (!form.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      historical_background: form.historical_background || '',
      description: form.description || '',
    }
    if (isEdit.value && editingId.value) {
      await http.put(`/themes/${editingId.value}`, payload)
    } else {
      await http.post('/themes', payload)
    }
    ElMessage.success('保存成功')
    open.value = false
    await load()
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '保存失败'
    ElMessage.error(typeof msg === 'string' ? msg : '保存失败')
  } finally {
    saving.value = false
  }
}

const removeRow = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除主题「${row.name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await http.delete(`/themes/${row.id}`)
    ElMessage.success('删除成功')
    await load()
  } catch {
    // 取消
  }
}

onMounted(() => {
  loadSlotConfigFromStorage()
  load()
})
</script>

<style scoped>
.theme-field-row {
  display: flex;
  gap: 10px;
  width: 100%;
  align-items: center;
}
.theme-field-row--top {
  align-items: flex-start;
}
.theme-field-row .el-input,
.theme-field-row .el-textarea {
  flex: 1;
  min-width: 0;
}
.theme-random-side {
  align-self: flex-start;
  margin-top: 4px;
}
.theme-btn-icon {
  margin-right: 4px;
  vertical-align: middle;
}
.theme-ai-submit {
  background: #1a1a1a;
  border-color: #1a1a1a;
  color: #fff;
}
.theme-ai-submit:hover {
  background: #333;
  border-color: #333;
  color: #fff;
}
.theme-config-hint {
  margin: 12px 0 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
</style>
