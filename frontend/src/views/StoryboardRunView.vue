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

    <el-card v-if="!isFrameDecompositionNode" shadow="never" style="margin-bottom: 12px">
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

    <el-card v-if="isFrameDecompositionNode && currentNode?.frameDecomposition" shadow="never" class="fd-panel">
      <div class="fd-toolbar">
        <span class="fd-filter-label">选择模块:</span>
        <el-select v-model="currentNode.frameDecomposition.filterModule" style="width: 220px">
          <el-option label="全部场景" value="all" />
          <el-option
            v-for="s in currentNode.frameDecomposition.scenes"
            :key="s.id"
            :label="s.title || '未命名场景'"
            :value="s.id"
          />
        </el-select>
      </div>

      <div class="fd-ai-block">
        <div class="fd-ai-label">AI辅助修改:</div>
        <div v-loading="submitLoading" element-loading-text="正在请求大模型，请稍候…" class="fd-ai-inner">
          <el-input
            v-model="currentNode.frameDecomposition.aiModifyText"
            type="textarea"
            :rows="6"
            :disabled="submitLoading"
            placeholder="在此输入新的分镜内容..."
          />
          <el-button type="primary" class="fd-ai-submit" :loading="submitLoading" :disabled="submitLoading" @click="runFrameDecompositionAi">
            提交
          </el-button>
        </div>
      </div>

      <div v-if="!filteredFrameDecompScenes.length" class="fd-empty">
        <p>暂无场景卡片。可提交「AI辅助修改」由模型生成，或手动新建场景。</p>
        <el-button type="success" plain @click="createEmptyFrameDecompScene">新建场景</el-button>
      </div>
      <div v-else class="fd-scene-list">
        <div v-for="s in filteredFrameDecompScenes" :key="s.id" class="fd-scene-card">
          <div class="fd-scene-head">
            <span class="fd-scene-title">{{ s.title || '未命名场景' }}</span>
            <el-button type="success" size="small" plain @click="openFrameDecompEdit(s)">编辑</el-button>
          </div>
          <div class="fd-scene-thumb" aria-hidden="true" />
          <div class="fd-frames">
            <div v-for="(fr, fi) in s.frames" :key="fr.id" class="fd-frame-line">
              <span class="fd-frame-label">画面{{ fi + 1 }}的描述:</span>
              <span class="fd-frame-text">{{ fr.description || '—' }}</span>
            </div>
            <div v-if="!s.frames?.length" class="fd-frame-empty">暂无画面描述</div>
          </div>
          <div class="fd-scene-footer">
            <span class="fd-scene-time">更新时间: {{ formatFdTime(s.updatedAt) }}</span>
          </div>
        </div>
      </div>

      <div class="fd-node-actions">
        <el-button type="primary" :disabled="submitLoading" @click="completeNode">保存并下一步</el-button>
        <el-button :disabled="submitLoading" @click="resetToCurrentNode">重置到当前节点</el-button>
      </div>
    </el-card>

    <el-dialog v-model="frameDecompEditOpen" title="编辑场景" width="560px" destroy-on-close @closed="frameDecompEditDraft = null">
      <template v-if="frameDecompEditDraft">
        <el-form label-width="88px">
          <el-form-item label="场景标题">
            <el-input v-model="frameDecompEditDraft.title" placeholder="例如：场景1：清晨的咖啡馆" />
          </el-form-item>
        </el-form>
        <div class="fd-edit-frames-head">画面描述</div>
        <div v-for="(fr, fi) in frameDecompEditDraft.frames" :key="fr.id" class="fd-edit-frame-row">
          <div class="fd-edit-frame-label">画面{{ fi + 1 }}</div>
          <el-input v-model="fr.description" type="textarea" :rows="2" placeholder="画面描述" />
          <el-button text type="danger" @click="removeFrameDecompFrame(fi)">删除</el-button>
        </div>
        <el-button type="primary" plain size="small" style="margin-top: 8px" @click="addFrameDecompEditFrame">添加画面</el-button>
      </template>
      <template #footer>
        <el-button @click="frameDecompEditOpen = false">取消</el-button>
        <el-button type="primary" @click="saveFrameDecompEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-card v-if="isSceneReviewNode" shadow="never" class="output-card">
      <div style="font-weight: 600; margin-bottom: 10px">输出</div>
      <template v-if="sceneReviewData">
        <div class="review-summary">
          <div class="review-summary-title">评审结果</div>
          <div v-if="sceneReviewData.conclusion" class="review-summary-conclusion">{{ sceneReviewData.conclusion }}</div>
          <ul v-if="sceneReviewData.issues?.length" class="review-summary-issues">
            <li v-for="(item, i) in sceneReviewData.issues" :key="i">{{ item }}</li>
          </ul>
        </div>
        <div class="review-compare">
          <div class="review-pane">
            <div class="review-pane-head">原内容</div>
            <div
              ref="reviewScrollLeftRef"
              class="review-pane-body review-font-original"
              @scroll="onReviewPaneScroll('left')"
            >
              <pre>{{ sceneReviewData.original || '（无）' }}</pre>
            </div>
          </div>
          <div class="review-pane">
            <div class="review-pane-head review-pane-head-row">
              <span>修改后</span>
              <el-button size="small" type="primary" :disabled="!sceneReviewData.revised" @click="copyRevisedContent">
                一键复制
              </el-button>
            </div>
            <div
              ref="reviewScrollRightRef"
              class="review-pane-body review-font-revised"
              @scroll="onReviewPaneScroll('right')"
            >
              <pre class="review-revised-pre">{{ sceneReviewData.revised || '（无）' }}</pre>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="review-parse-fallback">
        <el-alert type="info" show-icon :closable="false" title="未识别到结构化评审结果" description="请将模型输出为 JSON（含 评审结论、问题点、原内容、修改后 等字段），或使用下方「一键复制」后调整提示词重试。" />
        <div class="review-fallback-text">{{ currentOutputText || '暂无输出' }}</div>
        <el-button size="small" class="review-fallback-copy" :disabled="!currentOutputText" @click="copyOutput">一键复制全文</el-button>
      </div>
    </el-card>

    <el-card v-else-if="!isFrameDecompositionNode" shadow="never" class="output-card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
        <div style="font-weight: 600">输出</div>
        <el-button size="small" :disabled="!currentOutputText" @click="copyOutput">一键复制</el-button>
      </div>
      <div style="white-space: pre-wrap; min-height: 90px">{{ currentOutputText || '暂无输出' }}</div>
    </el-card>

    <el-card v-if="!isFrameDecompositionNode" shadow="never" style="margin-top: 12px">
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

const defaultNodes = () => {
  const t = Date.now()
  return [
    { id: `node-${t}-1`, name: '故事描述', inputText: '', outputText: '', completed: false, enabled: true, modelId: null, promptId: null },
    { id: `node-${t}-2`, name: '场景分解', inputText: '', outputText: '', completed: false, enabled: true, modelId: null, promptId: null },
    { id: `node-${t}-3`, name: '场景评审', inputText: '', outputText: '', completed: false, enabled: true, modelId: null, promptId: null },
    {
      id: `node-${t}-4`,
      name: '画面分解',
      inputText: '',
      outputText: '',
      completed: false,
      enabled: true,
      modelId: null,
      promptId: null,
      frameDecomposition: { filterModule: 'all', aiModifyText: '', scenes: [] },
    },
    { id: `node-${t}-5`, name: '画面评审', inputText: '', outputText: '', completed: false, enabled: true, modelId: null, promptId: null },
  ]
}

const currentNode = computed(() => nodes.value[activeNodeIndex.value] || null)
const defaultPromptMap = {
  故事描述: '根据主题与素材，用简洁中文写出故事梗概、人物动机与情绪走向，便于后续分镜。',
  场景分解: '将故事拆为若干场景：每个场景给出地点、时间、出场人物、冲突点与视觉重点。',
  场景评审:
    '你是对短视频分镜负责的场景编辑。请对比「原内容」与期望标准，输出严格 JSON（不要 markdown 代码块），格式如下：\n'
    + '{"评审结论":"整体评价与是否通过的结论（可多句）","问题点":["具体问题1","问题点2"],"原内容":"待评审的原文（若上文无原文可填用户提供的段落）","修改后":"修改润色后的完整正文"}\n'
    + '要求：问题点用列表；原内容与修改后均为纯文本字符串；修改后应保留原意并修正问题。',
  画面分解:
    '你是短视频分镜师。根据上游场景与评审结果，将内容整理为「按场景、按画面」的结构化分镜。\n'
    + '请输出严格 JSON（不要 markdown 代码块），格式如下：\n'
    + '{"scenes":[{"title":"场景1：标题简述","frames":[{"description":"画面1的描述: ..."},{"description":"画面2的描述: ..."}]}]}\n'
    + '每个场景包含若干画面；description 请用「画面N的描述:」前缀风格亦可直接写画面内容。若用户要求整体改写，在保留 scenes 数组结构的前提下替换文案。',
  画面评审: '从构图、光影、连贯性、可执行性评审画面描述，列出优点与改进建议，并给出优化后的画面说明列表。',
  // 兼容旧版默认节点名
  用户输入: '根据用户输入主题，梳理目标受众、场景设定和表达方向。',
  画面概述: '先产出整体画面风格与视觉基调，明确主色调和情绪。',
  镜头概述: '先产出整体画面风格与视觉基调，明确主色调和情绪。',
  镜头拆解: '按远景、中景、近景拆解镜头，并给出时长与运镜方式。',
  AI绘制: '输出用于图像生成的关键提示词，包含主体、环境、光影与风格。',
  分镜脚本: '整合镜头描述、旁白和转场，形成可执行分镜脚本。',
}
const defaultPromptText = computed(() => {
  if (!currentNode.value) return ''
  const promptRow = prompts.value.find((item) => item.id === currentNode.value.promptId)
  if (promptRow?.description) return promptRow.description
  return defaultPromptMap[currentNode.value.name] || `请围绕「${currentNode.value.name}」节点生成执行内容。`
})

const currentOutputText = computed(() => currentNode.value?.outputText ?? '')

const isSceneReviewNode = computed(() => currentNode.value?.name === '场景评审')
const isFrameDecompositionNode = computed(() => currentNode.value?.name === '画面分解')

const normalizeFdScene = (rawScene, si) => {
  const title = rawScene?.title ?? rawScene?.标题 ?? rawScene?.name ?? `场景${si + 1}`
  let framesRaw = rawScene?.frames ?? rawScene?.画面 ?? rawScene?.shots ?? rawScene?.画面列表
  if (!Array.isArray(framesRaw)) framesRaw = []
  const frames = framesRaw.map((f, fi) => {
    if (typeof f === 'string') {
      return { id: `fd-f-${si}-${fi}-${Date.now()}`, description: f }
    }
    const desc = f?.description ?? f?.描述 ?? f?.desc ?? f?.text ?? ''
    return { id: f?.id || `fd-f-${si}-${fi}-${Date.now()}`, description: String(desc) }
  })
  return {
    id: rawScene?.id || `fd-s-${si}-${Date.now()}`,
    title: String(title),
    frames,
    updatedAt: rawScene?.updatedAt || new Date().toISOString(),
  }
}

const parseFrameDecompositionJson = (raw) => {
  if (!raw || !String(raw).trim()) return null
  let text = String(raw).trim()
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i)
  if (fence) text = fence[1].trim()
  const brace = text.match(/\{[\s\S]*\}/)
  if (brace) text = brace[0]
  try {
    const o = JSON.parse(text)
    if (!o || typeof o !== 'object') return null
    let list = o.scenes ?? o.场景列表 ?? o.data
    if (!Array.isArray(list)) return null
    const scenes = list.map((rawScene, si) => normalizeFdScene(rawScene, si))
    if (!scenes.length) return null
    return { scenes }
  } catch {
    return null
  }
}

const emptyFrameDecomposition = () => ({
  filterModule: 'all',
  aiModifyText: '',
  scenes: [],
})

const syncFrameDecompToOutput = (node) => {
  if (!node?.frameDecomposition) return
  try {
    node.outputText = JSON.stringify({ scenes: node.frameDecomposition.scenes }, null, 2)
  } catch {
    node.outputText = ''
  }
}

const filteredFrameDecompScenes = computed(() => {
  const fd = currentNode.value?.frameDecomposition
  if (!fd?.scenes) return []
  if (fd.filterModule === 'all') return fd.scenes
  return fd.scenes.filter((s) => s.id === fd.filterModule)
})

const formatFdTime = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min}`
}

const ensureFrameDecompositionState = (node) => {
  if (!node || node.name !== '画面分解') return
  if (!node.frameDecomposition) {
    const parsed = parseFrameDecompositionJson(node.outputText)
    node.frameDecomposition = emptyFrameDecomposition()
    if (parsed?.scenes?.length) {
      node.frameDecomposition.scenes = parsed.scenes
    }
  }
}

watch(
  () => [activeNodeIndex.value, nodes.value],
  () => {
    const n = currentNode.value
    if (n?.name === '画面分解') ensureFrameDecompositionState(n)
  },
  { deep: true, immediate: true },
)

const runFrameDecompositionAi = async () => {
  if (!currentNode.value || currentNode.value.name !== '画面分解') return
  ensureFrameDecompositionState(currentNode.value)
  const fd = currentNode.value.frameDecomposition
  const userPart = fd.aiModifyText?.trim()
  const ctx =
    fd.scenes?.length > 0
      ? `\n当前分镜数据（请按需修改后输出完整 JSON）：\n${JSON.stringify({ scenes: fd.scenes }, null, 2)}`
      : ''
  const finalPrompt = [defaultPromptText.value, ctx, userPart].filter(Boolean).join('\n\n')
  if (!finalPrompt.trim()) {
    ElMessage.warning('请填写修改说明，或先通过「新建场景」添加内容以便模型参考')
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
      { timeout: 300000 },
    )
    const out = data.output_text || ''
    const parsed = parseFrameDecompositionJson(out)
    if (parsed?.scenes?.length) {
      fd.scenes = parsed.scenes.map((s, i) => ({
        ...s,
        updatedAt: new Date().toISOString(),
        id: s.id || `fd-s-${i}-${Date.now()}`,
      }))
      fd.filterModule = 'all'
      currentNode.value.outputText = out
      fd.aiModifyText = ''
      persistState()
      ElMessage.success('已更新场景卡片')
    } else {
      ElMessage.warning('模型未返回可解析的 JSON（需包含 scenes 数组），请调整说明后重试')
    }
  } catch (e) {
    const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(String(e?.message || ''))
    if (isTimeout) {
      ElMessage.error('请求超时（大模型响应较慢）。若网络正常可稍后重试。')
      return
    }
    const d = e?.response?.data?.detail
    const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg || x).join('; ') : '提交失败'
    ElMessage.error(msg)
  } finally {
    submitLoading.value = false
  }
}

const frameDecompEditOpen = ref(false)
const frameDecompEditDraft = ref(null)
const frameDecompEditingId = ref(null)

const openFrameDecompEdit = (sceneRow) => {
  ensureFrameDecompositionState(currentNode.value)
  frameDecompEditingId.value = sceneRow.id
  frameDecompEditDraft.value = JSON.parse(
    JSON.stringify({
      id: sceneRow.id,
      title: sceneRow.title,
      frames: (sceneRow.frames || []).map((f) => ({ ...f, description: f.description || '' })),
      updatedAt: sceneRow.updatedAt,
    }),
  )
  if (!frameDecompEditDraft.value.frames.length) {
    frameDecompEditDraft.value.frames.push({ id: `fd-f-new-${Date.now()}`, description: '' })
  }
  frameDecompEditOpen.value = true
}

const addFrameDecompEditFrame = () => {
  if (!frameDecompEditDraft.value) return
  frameDecompEditDraft.value.frames.push({ id: `fd-f-new-${Date.now()}`, description: '' })
}

const removeFrameDecompFrame = (fi) => {
  if (!frameDecompEditDraft.value?.frames) return
  frameDecompEditDraft.value.frames.splice(fi, 1)
}

const saveFrameDecompEdit = () => {
  const fd = currentNode.value?.frameDecomposition
  const draft = frameDecompEditDraft.value
  if (!fd || !draft) return
  const idx = fd.scenes.findIndex((s) => s.id === frameDecompEditingId.value)
  if (idx < 0) return
  fd.scenes[idx] = {
    id: draft.id,
    title: String(draft.title || '').trim() || `场景${idx + 1}`,
    frames: draft.frames.map((f, fi) => ({
      id: f.id || `fd-f-${fi}-${Date.now()}`,
      description: String(f.description || '').trim(),
    })),
    updatedAt: new Date().toISOString(),
  }
  syncFrameDecompToOutput(currentNode.value)
  persistState()
  frameDecompEditOpen.value = false
  ElMessage.success('已保存')
}

const createEmptyFrameDecompScene = () => {
  ensureFrameDecompositionState(currentNode.value)
  const fd = currentNode.value.frameDecomposition
  fd.filterModule = 'all'
  fd.scenes.push({
    id: `fd-s-${Date.now()}`,
    title: `场景${fd.scenes.length + 1}`,
    frames: [{ id: `fd-f-${Date.now()}`, description: '' }],
    updatedAt: new Date().toISOString(),
  })
  syncFrameDecompToOutput(currentNode.value)
  persistState()
  openFrameDecompEdit(fd.scenes[fd.scenes.length - 1])
}

/** 从模型输出中解析场景评审 JSON（支持中英文字段名） */
const parseSceneReviewJson = (raw) => {
  if (!raw || !String(raw).trim()) return null
  let text = String(raw).trim()
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i)
  if (fence) text = fence[1].trim()
  const brace = text.match(/\{[\s\S]*\}/)
  if (brace) text = brace[0]
  try {
    const o = JSON.parse(text)
    if (!o || typeof o !== 'object') return null
    const conclusion =
      o.评审结论 ?? o.conclusion ?? o.summary ?? o['评审结果'] ?? ''
    let issues = o.问题点 ?? o.issues ?? o.problems
    if (issues == null) issues = []
    if (!Array.isArray(issues)) issues = issues ? [String(issues)] : []
    issues = issues.map((x) => String(x))
    const original = o.原内容 ?? o.original ?? o.before ?? ''
    const revised = o.修改后 ?? o.revised ?? o.after ?? o.modified ?? ''
    if (!conclusion && !issues.length && !original && !revised) return null
    return {
      conclusion: String(conclusion || '').trim(),
      issues,
      original: String(original || ''),
      revised: String(revised || ''),
    }
  } catch {
    return null
  }
}

const sceneReviewData = computed(() => {
  if (!isSceneReviewNode.value) return null
  return parseSceneReviewJson(currentOutputText.value)
})

const reviewScrollLeftRef = ref(null)
const reviewScrollRightRef = ref(null)
const reviewScrollSuppress = ref(false)

const onReviewPaneScroll = (source) => {
  if (reviewScrollSuppress.value) return
  const left = reviewScrollLeftRef.value
  const right = reviewScrollRightRef.value
  if (!left || !right) return
  const src = source === 'left' ? left : right
  const dst = source === 'left' ? right : left
  const sh = src.scrollHeight - src.clientHeight
  const dh = dst.scrollHeight - dst.clientHeight
  if (sh <= 0 || dh <= 0) return
  const ratio = src.scrollTop / sh
  reviewScrollSuppress.value = true
  dst.scrollTop = ratio * dh
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      reviewScrollSuppress.value = false
    })
  })
}

watch([activeNodeIndex, currentOutputText], () => {
  reviewScrollSuppress.value = true
  nextTick(() => {
    const left = reviewScrollLeftRef.value
    const right = reviewScrollRightRef.value
    if (left) left.scrollTop = 0
    if (right) right.scrollTop = 0
    requestAnimationFrame(() => {
      reviewScrollSuppress.value = false
    })
  })
})

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
      frameDecomposition: node.frameDecomposition,
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
    frameDecomposition: i > idx ? undefined : node.frameDecomposition,
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

const copyRevisedContent = async () => {
  const text = sceneReviewData.value?.revised
  if (!text) {
    ElMessage.warning('暂无修改后内容')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制修改后内容')
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
      frameDecomposition: prev?.frameDecomposition ?? n.frameDecomposition,
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

.output-card {
  overflow: hidden;
}

.review-summary {
  background: linear-gradient(180deg, #e8f4ff 0%, #f0f7ff 100%);
  border: 1px solid #b3d8ff;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 14px;
}

.review-summary-title {
  font-weight: 700;
  font-size: 15px;
  color: #1a5fb4;
  margin-bottom: 10px;
}

.review-summary-conclusion {
  font-size: 14px;
  line-height: 1.65;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}

.review-summary-issues {
  margin: 10px 0 0;
  padding-left: 1.25rem;
  color: #606266;
  line-height: 1.6;
}

.review-compare {
  display: flex;
  gap: 12px;
  align-items: stretch;
  min-height: 280px;
}

.review-pane {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fafafa;
}

.review-pane-head {
  flex-shrink: 0;
  text-align: center;
  padding: 8px 12px;
  font-weight: 600;
  font-size: 13px;
  color: #606266;
  background: #eef0f3;
  border-bottom: 1px solid #e4e7ed;
}

.review-pane-head-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  text-align: left;
}

.review-pane-body {
  flex: 1;
  min-height: 220px;
  max-height: 420px;
  overflow: auto;
  padding: 12px;
  margin: 0;
  background: #fff;
}

.review-pane-body pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.55;
}

.review-font-original {
  font-family: ui-monospace, 'Cascadia Code', 'Consolas', 'Sarasa Mono SC', monospace;
  color: #c0392b;
}

.review-font-original pre {
  font-family: inherit;
  color: inherit;
}

.review-font-revised {
  font-family: 'Source Han Serif SC', 'Noto Serif SC', 'Georgia', 'Times New Roman', serif;
  color: #1e8449;
}

.review-revised-pre {
  font-family: inherit;
  color: inherit;
}

.review-parse-fallback {
  padding: 4px 0;
}

.review-fallback-text {
  margin-top: 12px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  min-height: 80px;
  font-size: 13px;
}

.review-fallback-copy {
  margin-top: 10px;
}

/* 画面分解 */
.fd-panel {
  margin-bottom: 12px;
}

.fd-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.fd-filter-label {
  font-size: 14px;
  color: #606266;
  flex-shrink: 0;
}

.fd-ai-block {
  margin-bottom: 20px;
}

.fd-ai-label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.fd-ai-inner {
  position: relative;
}

.fd-ai-submit {
  margin-top: 12px;
}

.fd-empty {
  padding: 24px;
  text-align: center;
  color: #909399;
  font-size: 14px;
  line-height: 1.6;
}

.fd-empty p {
  margin: 0 0 12px;
}

.fd-scene-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.fd-scene-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  padding: 0;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.fd-scene-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f9fafb;
  border-bottom: 1px solid #ebeef5;
}

.fd-scene-title {
  font-size: 15px;
  font-weight: 600;
  color: #409eff;
}

.fd-scene-thumb {
  height: 120px;
  margin: 12px 16px;
  border-radius: 8px;
  background: linear-gradient(135deg, #e8ecf0 0%, #d3d8de 50%, #c5cbd3 100%);
  filter: blur(0.3px);
  opacity: 0.92;
}

.fd-frames {
  padding: 8px 16px 4px;
  font-size: 14px;
  color: #303133;
  line-height: 1.65;
}

.fd-frame-line {
  margin-bottom: 10px;
}

.fd-frame-label {
  font-weight: 600;
  color: #606266;
  margin-right: 6px;
}

.fd-frame-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.fd-frame-empty {
  color: #909399;
  font-size: 13px;
  padding: 8px 0;
}

.fd-scene-footer {
  margin: 0 16px 14px;
  padding-top: 10px;
  border-top: 1px dashed #dcdfe6;
}

.fd-scene-time {
  font-size: 12px;
  color: #909399;
}

.fd-node-actions {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.fd-edit-frames-head {
  font-weight: 600;
  margin: 12px 0 8px;
  font-size: 14px;
}

.fd-edit-frame-row {
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.fd-edit-frame-label {
  font-size: 13px;
  color: #606266;
}
</style>
