<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div>
          <el-button link @click="goBack">返回</el-button>
          <span style="margin-left: 8px; font-weight: 600">场景详情：{{ scene?.name || '加载中' }}</span>
        </div>
        <div style="display: flex; gap: 8px; align-items: center">
          <el-tag type="info">共 {{ nodes.length }} 个节点</el-tag>
          <el-button type="primary" @click="openCustomNodeDialog">自定义节点</el-button>
        </div>
      </div>
    </template>

    <el-steps :active="activeNodeIndex" finish-status="success" align-center class="flow-steps">
      <el-step
        v-for="(node, idx) in nodes"
        :key="`flow-${node.id}`"
        :status="node.completed ? 'success' : idx === activeNodeIndex ? 'process' : 'wait'"
      >
        <template #icon>
          <button
            type="button"
            class="step-icon-btn"
            :class="{
              'is-current': idx === activeNodeIndex,
              'is-completed': node.completed,
              'is-unlocked': isNodeUnlocked(idx),
            }"
            :disabled="!canViewNodeDetail(idx)"
            @click="openNode(idx)"
          >
            {{ idx === activeNodeIndex ? idx + 1 : node.completed ? '✓' : idx + 1 }}
          </button>
        </template>
        <template #title>
          <button
            type="button"
            class="step-title-btn"
            :class="{
              'is-current': idx === activeNodeIndex,
              'is-completed': node.completed,
              'is-unlocked': isNodeUnlocked(idx),
            }"
            :disabled="!canViewNodeDetail(idx)"
            @click="openNode(idx)"
          >
            {{ node.name }}
          </button>
        </template>
      </el-step>
    </el-steps>

    <el-card shadow="never" style="margin-bottom: 12px">
      <div style="font-weight: 600; margin-bottom: 8px">输入自定义提示词</div>
      <div
        v-if="currentNode"
        v-loading="submitLoading"
        element-loading-text="正在请求大模型，请稍候…"
        style="position: relative; min-height: 120px"
      >
        <el-input
          v-model="currentNode.inputText"
          type="textarea"
          :rows="4"
          :disabled="submitLoading"
          placeholder="可输入补充要求，例如：风格更二次元、运镜更流畅..."
        />
      </div>
      <div v-else>暂无节点，请先新增节点。</div>
      <div style="margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap">
        <el-button type="primary" :disabled="!currentNode || submitLoading" :loading="submitLoading" @click="runCurrentNode">
          提交
        </el-button>
        <el-button :disabled="!currentNode || submitLoading" @click="completeNode">保存并下一步</el-button>
        <el-button :disabled="!currentNode || submitLoading" @click="resetToCurrentNode">重置到当前节点</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
        <div style="font-weight: 600">输出</div>
        <el-button size="small" :disabled="!currentOutputText" @click="copyOutput">一键复制</el-button>
      </div>
      <div style="white-space: pre-wrap; min-height: 90px">{{ currentOutputText || '暂无输出' }}</div>
    </el-card>

    <el-card shadow="never" style="margin-top: 12px">
      <div style="font-weight: 600; margin-bottom: 8px">默认提示词</div>
      <el-input :model-value="defaultPromptText" type="textarea" :rows="3" readonly />
    </el-card>
  </el-card>

  <el-dialog v-model="customNodeDialogOpen" title="自定义节点配置" width="980px">
    <div style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center">
      <span>拖拽行首图标可调整节点顺序</span>
      <el-button type="primary" plain @click="appendEditableNode">新增节点</el-button>
    </div>
    <el-table ref="customNodeTableRef" :data="editableNodes" row-key="id" border>
      <el-table-column label="" width="48">
        <template #default>
          <span class="drag-handle" style="cursor: move">☰</span>
        </template>
      </el-table-column>
      <el-table-column label="节点名称" min-width="140">
        <template #default="scope">
          <el-input v-model="scope.row.name" />
        </template>
      </el-table-column>
      <el-table-column label="模型" min-width="160">
        <template #default="scope">
          <el-select v-model="scope.row.modelId" placeholder="选择模型" clearable style="width: 100%">
            <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="提示词" min-width="180">
        <template #default="scope">
          <el-select v-model="scope.row.promptId" placeholder="选择提示词" clearable style="width: 100%">
            <el-option v-for="p in prompts" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="是否启用" width="100">
        <template #default="scope">
          <el-switch v-model="scope.row.enabled" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="scope">
          <el-button text type="danger" @click="removeEditableNode(scope.$index)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="customNodeDialogOpen = false">取消</el-button>
      <el-button type="primary" @click="saveCustomNodes">保存节点配置</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Sortable from 'sortablejs'
import http from '../api/http'

const route = useRoute()
const router = useRouter()
const sceneId = Number(route.params.id)
const scene = ref(null)
const submitLoading = ref(false)
const activeNodeIndex = ref(0)
const maxUnlockedIndex = ref(0)
const nodes = ref([])
const customNodeDialogOpen = ref(false)
const customNodeTableRef = ref(null)
const editableNodes = ref([])
const models = ref([])
const prompts = ref([])
const sortableInstance = ref(null)

const STORAGE_KEY = computed(() => `storyboard-run-state:${sceneId}`)

const defaultNodes = () => [
  { id: `node-${Date.now()}-1`, name: '用户输入', inputText: '', outputText: '', completed: false, enabled: true, modelId: null, promptId: null },
  { id: `node-${Date.now()}-2`, name: '镜头概述', inputText: '', outputText: '', completed: false, enabled: true, modelId: null, promptId: null },
  { id: `node-${Date.now()}-3`, name: '镜头拆解', inputText: '', outputText: '', completed: false, enabled: true, modelId: null, promptId: null },
  { id: `node-${Date.now()}-4`, name: 'AI绘制', inputText: '', outputText: '', completed: false, enabled: true, modelId: null, promptId: null },
  { id: `node-${Date.now()}-5`, name: '分镜脚本', inputText: '', outputText: '', completed: false, enabled: true, modelId: null, promptId: null },
]

const currentNode = computed(() => nodes.value[activeNodeIndex.value] || null)
const defaultPromptMap = {
  '用户输入': '根据用户输入主题，梳理目标受众、场景设定和表达方向。',
  '画面概述': '先产出整体画面风格与视觉基调，明确主色调和情绪。',
  '镜头概述': '先产出整体画面风格与视觉基调，明确主色调和情绪。',
  '镜头拆解': '按远景、中景、近景拆解镜头，并给出时长与运镜方式。',
  'AI绘制': '输出用于图像生成的关键提示词，包含主体、环境、光影与风格。',
  '分镜脚本': '整合镜头描述、旁白和转场，形成可执行分镜脚本。',
}
const defaultPromptText = computed(() => {
  if (!currentNode.value) return ''
  const promptRow = prompts.value.find((item) => item.id === currentNode.value.promptId)
  if (promptRow?.description) return promptRow.description
  return defaultPromptMap[currentNode.value.name] || `请围绕「${currentNode.value.name}」节点生成执行内容。`
})

const currentOutputText = computed(() => currentNode.value?.outputText ?? '')

const persistState = () => {
  localStorage.setItem(
    STORAGE_KEY.value,
    JSON.stringify({
      activeNodeIndex: activeNodeIndex.value,
      maxUnlockedIndex: maxUnlockedIndex.value,
      nodes: nodes.value,
    })
  )
}

const loadState = () => {
  const raw = localStorage.getItem(STORAGE_KEY.value)
  if (!raw) {
    nodes.value = defaultNodes()
    activeNodeIndex.value = 0
    maxUnlockedIndex.value = 0
    return
  }
  try {
    const parsed = JSON.parse(raw)
    nodes.value = Array.isArray(parsed.nodes) && parsed.nodes.length ? parsed.nodes : defaultNodes()
    nodes.value = nodes.value.map((node) => ({
      enabled: true,
      modelId: null,
      promptId: null,
      ...node,
      outputText: node.outputText ?? '',
      inputText: node.inputText ?? '',
    }))
    activeNodeIndex.value = Number.isInteger(parsed.activeNodeIndex) ? parsed.activeNodeIndex : 0
    maxUnlockedIndex.value = Number.isInteger(parsed.maxUnlockedIndex)
      ? parsed.maxUnlockedIndex
      : Math.max(activeNodeIndex.value, 0)
    if (activeNodeIndex.value >= nodes.value.length) activeNodeIndex.value = 0
    if (maxUnlockedIndex.value >= nodes.value.length) maxUnlockedIndex.value = nodes.value.length - 1
  } catch {
    nodes.value = defaultNodes()
    activeNodeIndex.value = 0
    maxUnlockedIndex.value = 0
  }
}

const canViewNodeDetail = (idx) => {
  const node = nodes.value[idx]
  if (!node || node.enabled === false) return false
  return idx <= maxUnlockedIndex.value
}

const isNodeUnlocked = (idx) => idx <= maxUnlockedIndex.value

const openNode = (idx) => {
  if (!canViewNodeDetail(idx)) return
  activeNodeIndex.value = idx
  persistState()
}

const appendEditableNode = () => {
  editableNodes.value.push({
    id: `node-${Date.now()}`,
    name: `自定义节点${editableNodes.value.length + 1}`,
    inputText: '',
    outputText: '',
    completed: false,
    enabled: true,
    modelId: null,
    promptId: null,
  })
}

const removeEditableNode = (idx) => {
  editableNodes.value.splice(idx, 1)
}

const removeActiveNode = () => {
  if (!currentNode.value) return
  if (nodes.value.length <= 1) {
    ElMessage.warning('至少保留一个节点')
    return
  }
  nodes.value.splice(activeNodeIndex.value, 1)
  if (activeNodeIndex.value >= nodes.value.length) activeNodeIndex.value = nodes.value.length - 1
  if (maxUnlockedIndex.value >= nodes.value.length) maxUnlockedIndex.value = nodes.value.length - 1
  persistState()
  ElMessage.success('节点已删除')
}

const resetToNode = (idx) => {
  if (idx < 0 || idx >= nodes.value.length) return
  nodes.value = nodes.value.map((node, i) => ({
    ...node,
    completed: i < idx ? node.completed : false,
    inputText: i > idx ? '' : (node.inputText ?? ''),
    outputText: i > idx ? '' : (node.outputText ?? ''),
  }))
  activeNodeIndex.value = idx
  if (idx > maxUnlockedIndex.value) maxUnlockedIndex.value = idx
  maxUnlockedIndex.value = idx
  persistState()
  ElMessage.success(`已重置到节点：${nodes.value[idx].name}`)
}

const resetToCurrentNode = () => resetToNode(activeNodeIndex.value)

const completeNode = () => {
  if (!currentNode.value) return
  currentNode.value.completed = true
  let next = activeNodeIndex.value + 1
  while (next < nodes.value.length && nodes.value[next].enabled === false) next += 1
  if (next < nodes.value.length) {
    activeNodeIndex.value = next
    if (next > maxUnlockedIndex.value) maxUnlockedIndex.value = next
  }
  persistState()
  ElMessage.success('节点已完成')
}

const runCurrentNode = async () => {
  if (!currentNode.value) return
  const customText = currentNode.value.inputText?.trim()
  const finalPrompt = [defaultPromptText.value, customText].filter(Boolean).join('\n')
  if (!finalPrompt.trim()) {
    ElMessage.warning('预置提示词与自定义提示词至少填写一项')
    return
  }
  submitLoading.value = true
  try {
    const { data } = await http.post(
      `/storyboards/${sceneId}/run`,
      {
        input_text: finalPrompt,
        model_id: currentNode.value.modelId ?? null,
      },
      { timeout: 300000 }
    )
    currentNode.value.outputText = data.output_text || ''
    persistState()
    ElMessage.success('提交成功')
  } catch (e) {
    const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(String(e?.message || ''))
    if (isTimeout) {
      ElMessage.error('请求超时（大模型响应较慢）。若网络正常可稍后重试；仍失败可检查后端到模型服务的延迟。')
      return
    }
    const d = e?.response?.data?.detail
    const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg || x).join('; ') : '提交失败'
    ElMessage.error(msg)
  } finally {
    submitLoading.value = false
  }
}

const copyOutput = async () => {
  const text = currentOutputText.value
  if (!text) {
    ElMessage.warning('暂无可复制内容')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const fetchScene = async () => {
  const { data } = await http.get('/storyboards')
  scene.value = data.find((item) => item.id === sceneId) || null
}

const fetchNodeOptions = async () => {
  const [modelsRes, promptsRes] = await Promise.all([http.get('/llm/models'), http.get('/prompts')])
  models.value = modelsRes.data || []
  prompts.value = promptsRes.data || []
}

const openCustomNodeDialog = async () => {
  await fetchNodeOptions()
  editableNodes.value = nodes.value.map((node) => ({ ...node }))
  customNodeDialogOpen.value = true
}

const saveCustomNodes = () => {
  const prevById = Object.fromEntries(nodes.value.map((n) => [n.id, n]))
  const validNodes = editableNodes.value
    .map((node) => ({ ...node, name: String(node.name || '').trim() }))
    .filter((node) => node.name)
  if (!validNodes.length) {
    ElMessage.warning('至少保留一个有效节点')
    return
  }
  nodes.value = validNodes.map((n) => {
    const prev = prevById[n.id]
    return {
      ...n,
      inputText: prev?.inputText ?? n.inputText ?? '',
      outputText: prev?.outputText ?? n.outputText ?? '',
      completed: prev?.completed ?? n.completed ?? false,
    }
  })
  if (activeNodeIndex.value >= nodes.value.length) activeNodeIndex.value = nodes.value.length - 1
  if (nodes.value[activeNodeIndex.value]?.enabled === false) {
    const firstEnabled = nodes.value.findIndex((item) => item.enabled !== false)
    activeNodeIndex.value = firstEnabled >= 0 ? firstEnabled : 0
  }
  persistState()
  customNodeDialogOpen.value = false
  ElMessage.success('节点配置已保存')
}

const initSortable = async () => {
  await nextTick()
  const tbody = customNodeTableRef.value?.$el?.querySelector('.el-table__body-wrapper tbody')
  if (!tbody) return
  sortableInstance.value?.destroy()
  sortableInstance.value = Sortable.create(tbody, {
    handle: '.drag-handle',
    animation: 150,
    onEnd(evt) {
      const list = [...editableNodes.value]
      const [moved] = list.splice(evt.oldIndex, 1)
      list.splice(evt.newIndex, 0, moved)
      editableNodes.value = list
    },
  })
}

watch(customNodeDialogOpen, (open) => {
  if (open) {
    initSortable()
  } else {
    sortableInstance.value?.destroy()
    sortableInstance.value = null
  }
})

const goBack = () => {
  router.push('/storyboards')
}

onMounted(async () => {
  loadState()
  if (maxUnlockedIndex.value < activeNodeIndex.value) maxUnlockedIndex.value = activeNodeIndex.value
  await fetchNodeOptions()
  await fetchScene()
  persistState()
})
</script>

<style scoped>
.flow-steps {
  margin-bottom: 14px;
}

.step-icon-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid #dcdfe6;
  background: #fff;
  color: #909399;
  cursor: pointer;
  font-size: 13px;
}

.step-icon-btn.is-current {
  border-color: #409eff;
  background: #409eff;
  color: #fff;
}

.step-icon-btn.is-unlocked:not(.is-current):not(.is-completed) {
  border-color: #409eff;
  color: #409eff;
}

.step-icon-btn.is-completed {
  border-color: #67c23a;
  background: #67c23a;
  color: #fff;
}

.step-icon-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.step-title-btn {
  border: none;
  background: transparent;
  color: #909399;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.step-title-btn.is-current {
  color: #fff;
  font-weight: 600;
  background: #333;
}

.step-title-btn.is-completed {
  color: #67c23a;
}

.step-title-btn.is-unlocked:not(.is-current):not(.is-completed) {
  color: #409eff;
}

.step-title-btn:disabled {
  color: #c0c4cc;
  cursor: not-allowed;
}
</style>
