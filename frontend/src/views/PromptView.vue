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
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="description" label="描述" />
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

  <el-dialog v-model="open" :title="isEdit ? '编辑模板' : '新增模板'" width="600px">
    <el-form :model="form" label-width="90px">
      <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="6" /></el-form-item>
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
const form = reactive({ name: '', description: '' })
const keyword = ref('')
const onlyEnabled = ref(false)

const load = async () => {
  const { data } = await http.get('/prompts')
  rows.value = data
  runSearch()
}

const normalizedKeyword = computed(() => keyword.value.trim().toLowerCase())

const runSearch = () => {
  const key = normalizedKeyword.value
  filteredRows.value = rows.value.filter((row) => {
    const hitEnabled = !onlyEnabled.value || row.enabled
    if (!hitEnabled) return false
    if (!key) return true
    const name = String(row.name || '').toLowerCase()
    const desc = String(row.description || '').toLowerCase()
    return name.includes(key) || desc.includes(key)
  })
}

const resetForm = () => {
  isEdit.value = false
  editingId.value = null
  form.name = ''
  form.description = ''
}

const openCreate = () => {
  resetForm()
  open.value = true
}

const openEdit = (row) => {
  isEdit.value = true
  editingId.value = row.id
  form.name = row.name
  form.description = row.description
  open.value = true
}

const save = async () => {
  if (isEdit.value && editingId.value) {
    await http.put(`/prompts/${editingId.value}`, form)
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
    await http.patch(`/prompts/${row.id}/enabled`, { enabled })
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
    await http.delete(`/prompts/${row.id}`)
    ElMessage.success('删除成功')
    await load()
  } catch {
    // 用户取消删除
  }
}

onMounted(load)
</script>
