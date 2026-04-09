<template>
  <el-card>
    <template #header>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span>分镜列表</span>
        <el-button type="primary" @click="openCreate">新增分镜</el-button>
      </div>
    </template>
    <el-table :data="rows" style="width:100%">
      <el-table-column prop="name" label="分镜名称" />
      <el-table-column prop="created_at" label="创建时间" />
      <el-table-column label="进度">
        <template #default="scope">
          <el-progress :percentage="getProgressPercent(scope.row.id)" :stroke-width="12" />
          <div style="margin-top: 4px; font-size: 12px; color: #909399">
            {{ getProgressText(scope.row.id) }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="scope">
          <el-button link type="primary" @click="edit(scope.row)">编辑</el-button>
          <el-button link type="primary" @click="run(scope.row)">运行分镜</el-button>
          <el-button link type="danger" @click="removeRow(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="open" :title="isEdit ? '编辑分镜' : '新增分镜'" width="500px">
    <el-form :model="form" label-width="90px">
      <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="4" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="open = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>

</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'

const router = useRouter()
const rows = ref([])
const open = ref(false)
const isEdit = ref(false)
const editingId = ref(null)
const form = reactive({ name: '', description: '' })

const load = async () => {
  const { data } = await http.get('/storyboards')
  rows.value = data
}

const getNodeStats = (sceneId) => {
  try {
    const raw = localStorage.getItem(`storyboard-run-state:${sceneId}`)
    if (!raw) return { completed: 0, total: 0 }
    const parsed = JSON.parse(raw)
    const nodes = Array.isArray(parsed?.nodes) ? parsed.nodes : []
    const total = nodes.length
    const completed = nodes.filter((node) => node?.completed).length
    return { completed, total }
  } catch {
    return { completed: 0, total: 0 }
  }
}

const getProgressPercent = (sceneId) => {
  const { completed, total } = getNodeStats(sceneId)
  if (!total) return 0
  return Math.round((completed / total) * 100)
}

const getProgressText = (sceneId) => {
  const { completed, total } = getNodeStats(sceneId)
  if (!total) return '0 / 0'
  return `${completed} / ${total}`
}

const openCreate = () => {
  isEdit.value = false
  editingId.value = null
  form.name = ''
  form.description = ''
  open.value = true
}

const save = async () => {
  if (isEdit.value && editingId.value) {
    await http.put(`/storyboards/${editingId.value}`, form)
  } else {
    await http.post('/storyboards', form)
  }
  ElMessage.success('保存成功')
  open.value = false
  isEdit.value = false
  editingId.value = null
  form.name = ''
  form.description = ''
  await load()
}

const edit = (row) => {
  isEdit.value = true
  editingId.value = row.id
  form.name = row.name
  form.description = row.description || ''
  open.value = true
}

const removeRow = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除分镜「${row.name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await http.delete(`/storyboards/${row.id}`)
    ElMessage.success('删除成功')
    await load()
  } catch {
    // 用户取消删除时不提示错误
  }
}

const run = (row) => {
  router.push(`/storyboards/${row.id}/run`)
}

onMounted(load)
</script>
