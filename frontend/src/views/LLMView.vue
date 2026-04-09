<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>模型管理（LLM 配置）</span>
        <el-button type="primary" @click="openCreate">新增</el-button>
      </div>
    </template>
    <el-table :data="rows" style="width: 100%">
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column prop="base_url" label="地址" min-width="200" show-overflow-tooltip />
      <el-table-column prop="model_name" label="模型" min-width="120" />
      <el-table-column label="状态" width="100">
        <template #default="scope">
          <el-switch :model-value="scope.row.enabled" @change="(v) => toggleEnabled(scope.row, v)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="scope">
          <el-button link type="primary" @click="openEdit(scope.row)">编辑</el-button>
          <el-button link type="danger" @click="removeRow(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="open" :title="isEdit ? '编辑配置' : '新增配置'" width="600px">
    <el-form :model="form" label-width="90px">
      <el-form-item label="名称">
        <el-input v-model="form.name" placeholder="配置显示名称" />
      </el-form-item>
      <el-form-item label="地址">
        <el-input v-model="form.base_url" placeholder="例如 https://api.openai.com/v1" />
      </el-form-item>
      <el-form-item label="Key">
        <el-input
          v-model="form.api_key"
          type="password"
          show-password
          placeholder="API Key"
          autocomplete="new-password"
        />
      </el-form-item>
      <el-form-item label="模型">
        <div style="display: flex; gap: 8px; width: 100%; align-items: center">
          <el-select
            v-model="form.model_name"
            filterable
            clearable
            :filter-method="handleModelSearch"
            placeholder="从列表中搜索并选择模型"
            style="flex: 1"
            @visible-change="onModelDropdownVisible"
          >
            <el-option v-for="m in filteredModelOptions" :key="m" :label="m" :value="m" />
          </el-select>
          <el-button :loading="remoteLoading" @click="fetchRemoteModels">刷新</el-button>
        </div>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" plain :loading="testLoading" @click="doTestConnection">测试连接性</el-button>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="open = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'

const rows = ref([])
const open = ref(false)
const isEdit = ref(false)
const editingId = ref(null)
const remoteModelOptions = ref([])
const filteredModelOptions = ref([])
const remoteLoading = ref(false)
const testLoading = ref(false)

const form = reactive({
  name: '',
  provider: 'openai',
  base_url: '',
  model_name: '',
  api_key: '',
  enabled: true,
})

const resetForm = () => {
  isEdit.value = false
  editingId.value = null
  form.name = ''
  form.provider = 'openai'
  form.base_url = ''
  form.model_name = ''
  form.api_key = ''
  form.enabled = true
  remoteModelOptions.value = []
  filteredModelOptions.value = []
}

const load = async () => {
  const { data } = await http.get('/llm/models')
  rows.value = data
}

const openCreate = () => {
  resetForm()
  open.value = true
}

const openEdit = (row) => {
  isEdit.value = true
  editingId.value = row.id
  form.name = row.name
  form.provider = row.provider || 'openai'
  form.base_url = row.base_url
  form.model_name = row.model_name
  form.api_key = row.api_key
  form.enabled = row.enabled
  remoteModelOptions.value = row.model_name ? [row.model_name] : []
  filteredModelOptions.value = [...remoteModelOptions.value]
  open.value = true
}

const fetchRemoteModels = async () => {
  const url = form.base_url.trim()
  if (!url) {
    ElMessage.warning('请先输入地址')
    return
  }
  remoteLoading.value = true
  try {
    const { data } = await http.post('/llm/remote-models', {
      base_url: url,
      api_key: form.api_key || '',
    })
    if (data.error) {
      ElMessage.error(data.error)
      return
    }
    remoteModelOptions.value = data.models || []
    filteredModelOptions.value = [...remoteModelOptions.value]
    if (remoteModelOptions.value.length && !form.model_name) {
      form.model_name = remoteModelOptions.value[0]
    }
    if (remoteModelOptions.value.length) {
      ElMessage.success(`已获取 ${remoteModelOptions.value.length} 个模型`)
    } else {
      ElMessage.info('未获取到模型列表')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '拉取模型失败')
  } finally {
    remoteLoading.value = false
  }
}

const handleModelSearch = (keyword) => {
  const q = String(keyword || '').trim().toLowerCase()
  if (!q) {
    filteredModelOptions.value = [...remoteModelOptions.value]
    return
  }
  filteredModelOptions.value = remoteModelOptions.value.filter((item) =>
    String(item).toLowerCase().includes(q)
  )
}

const onModelDropdownVisible = (visible) => {
  if (visible) handleModelSearch('')
}

const doTestConnection = async () => {
  const url = form.base_url.trim()
  if (!url) {
    ElMessage.warning('请先输入地址')
    return
  }
  testLoading.value = true
  try {
    const { data } = await http.post('/llm/test-connection', {
      base_url: url,
      api_key: form.api_key || '',
      model_name: form.model_name || null,
    })
    if (data.ok) {
      ElMessage.success(data.message)
    } else {
      ElMessage.error(data.message)
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '测试失败')
  } finally {
    testLoading.value = false
  }
}

const save = async () => {
  if (isEdit.value && editingId.value) {
    await http.put(`/llm/models/${editingId.value}`, form)
  } else {
    await http.post('/llm/models', form)
  }
  ElMessage.success('保存成功')
  open.value = false
  resetForm()
  await load()
}

const toggleEnabled = async (row, enabled) => {
  try {
    await http.patch(`/llm/models/${row.id}/enabled`, { enabled })
    row.enabled = enabled
    ElMessage.success('状态已更新')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '更新失败')
    await load()
  }
}

const removeRow = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除「${row.name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await http.delete(`/llm/models/${row.id}`)
    ElMessage.success('删除成功')
    await load()
  } catch {
    // 取消
  }
}

onMounted(load)
</script>
