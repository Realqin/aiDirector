<template>
  <el-card>
    <template #header>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span>提示词模板</span>
        <el-button type="primary" @click="openCreate">新增模板</el-button>
      </div>
    </template>
    <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
      <el-input
        v-model="keyword"
        placeholder="输入名称或描述"
        clearable
        style="width:280px"
        @keyup.enter="runSearch"
      />
      <el-button type="primary" @click="runSearch">查询</el-button>
      <el-checkbox v-model="onlyEnabled" @change="runSearch">仅看已启用</el-checkbox>
    </div>

    <el-table :data="filteredRows">
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column label="返回格式" width="110">
        <template #default="scope">
          <el-tag size="small" type="info">{{ formatLabel(scope.row.response_format) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="正文预览" min-width="200" show-overflow-tooltip>
        <template #default="scope">
          {{ previewText(scope.row.description) }}
        </template>
      </el-table-column>
      <el-table-column label="启用状态" width="120">
        <template #default="scope">
          <el-switch
            v-model="scope.row.enabled"
            @change="(val) => toggleEnabled(scope.row, val)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="scope">
          <el-button link type="primary" @click="openEdit(scope.row)">编辑</el-button>
          <el-button link type="danger" @click="removeRow(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="open" :title="isEdit ? '编辑模板' : '新增模板'" width="720px" destroy-on-close>
    <el-form :model="form" label-width="120px">
      <el-form-item label="名称"><el-input v-model="form.name" placeholder="模板名称，唯一" /></el-form-item>
      <el-form-item label="提示词正文">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="8"
          placeholder="角色、任务、业务约束等；完整 JSON/Markdown 骨架请写在下方「输出格式示例」，勿重复粘贴到正文。"
        />
        <div class="form-hint">输出形态由下方「返回格式」与「格式示例」统一约束，修改正文不会影响格式区内容。</div>
      </el-form-item>
      <el-form-item label="返回格式">
        <el-select v-model="form.response_format" placeholder="选择模型输出形态" style="width: 100%">
          <el-option label="JSON" value="json" />
          <el-option label="纯文本" value="text" />
          <el-option label="Markdown" value="markdown" />
        </el-select>
        <div class="form-hint">与上方正文分离；将与「输出格式示例」一并拼入发给模型的提示。</div>
      </el-form-item>
      <el-form-item label="输出格式示例">
        <el-input
          v-model="form.format_example"
          type="textarea"
          :rows="5"
          placeholder="例如 JSON 样例、Markdown 标题层级样例等；与「返回格式」说明自动拼接，独立于正文。"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="open = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'

const rows = ref([])
const filteredRows = ref([])
const open = ref(false)
const isEdit = ref(false)
const editingId = ref(null)
const form = reactive({
  name: '',
  description: '',
  response_format: 'text',
  format_example: '',
})
const keyword = ref('')
const onlyEnabled = ref(false)

const load = async () => {
  const { data } = await http.get('/prompts')
  rows.value = data
  runSearch()
}

const normalizedKeyword = computed(() => keyword.value.trim().toLowerCase())

const formatLabel = (fmt) => {
  const m = { json: 'JSON', text: '纯文本', markdown: 'Markdown' }
  return m[String(fmt || '').toLowerCase()] || '纯文本'
}

const previewText = (s, max = 80) => {
  const t = String(s || '').replace(/\s+/g, ' ').trim()
  if (!t) return '—'
  return t.length <= max ? t : `${t.slice(0, max)}…`
}

const runSearch = () => {
  const key = normalizedKeyword.value
  filteredRows.value = rows.value.filter((row) => {
    const hitEnabled = !onlyEnabled.value || row.enabled
    if (!hitEnabled) return false
    if (!key) return true
    const name = String(row.name || '').toLowerCase()
    const desc = String(row.description || '').toLowerCase()
    const ex = String(row.format_example || '').toLowerCase()
    return name.includes(key) || desc.includes(key) || ex.includes(key)
  })
}

const resetForm = () => {
  isEdit.value = false
  editingId.value = null
  form.name = ''
  form.description = ''
  form.response_format = 'text'
  form.format_example = ''
}

const openCreate = () => {
  resetForm()
  open.value = true
}

const openEdit = (row) => {
  isEdit.value = true
  editingId.value = row.id
  form.name = row.name
  form.description = row.description || ''
  form.response_format = row.response_format || 'text'
  form.format_example = row.format_example || ''
  open.value = true
}

const save = async () => {
  if (isEdit.value && editingId.value) {
    await http.post('/prompts/update', { prompt_id: editingId.value, ...form })
  } else {
    await http.post('/prompts', form)
  }
  ElMessage.success('保存成功')
  open.value = false
  resetForm()
  await load()
}

const toggleEnabled = async (row, enabled) => {
  try {
    await http.post('/prompts/set-enabled', { prompt_id: row.id, enabled })
    ElMessage.success('状态已更新')
    runSearch()
  } catch {
    row.enabled = !enabled
    ElMessage.error('状态更新失败')
  }
}

const removeRow = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除模板「${row.name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await http.post('/prompts/delete', { prompt_id: row.id })
    ElMessage.success('删除成功')
    await load()
  } catch {
    // 用户取消删除
  }
}

onMounted(load)
</script>

<style scoped>
.form-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
</style>
