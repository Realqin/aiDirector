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

    <el-collapse v-if="aiRunDiagnostics" class="run-ctx-collapse">
      <el-collapse-item
        v-if="aiRunDiagnostics.summary != null"
        title="服务端：分镜与主题（POST …/ai-run/summary）"
        name="sum"
      >
        <pre class="run-ctx-pre">{{ JSON.stringify(aiRunDiagnostics.summary, null, 2) }}</pre>
      </el-collapse-item>
      <el-collapse-item
        v-if="aiRunDiagnostics.scene_tree != null"
        title="服务端：入库场景→画面树（POST …/ai-run/scene-frame-tree）"
        name="tree"
      >
        <pre class="run-ctx-pre">{{ JSON.stringify(aiRunDiagnostics.scene_tree, null, 2) }}</pre>
      </el-collapse-item>
      <el-collapse-item title="服务端：当前流水线节点（POST …/ai-run/pipeline-node）" name="node">
        <pre class="run-ctx-pre">{{ JSON.stringify(aiRunDiagnostics.pipeline_node, null, 2) }}</pre>
      </el-collapse-item>
    </el-collapse>

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

    <el-alert
      v-if="currentNode && isCompletedNodeReadonly"
      type="info"
      :closable="false"
      show-icon
      class="node-readonly-banner"
      title="当前节点已完成"
      description="内容已入表保存，仅支持查看；若要再次编辑或整页重新生成，请先点击「重置到当前节点」。"
    />

    <el-card v-if="!isFrameDecompositionNode && !isSceneDecompositionNode && !isFullContentGenNode" shadow="never" style="margin-bottom: 12px">
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
          :disabled="submitLoading || isCompletedNodeReadonly"
          placeholder="可输入补充要求，例如：风格更二次元、运镜更流畅..."
        />
      </div>
      <div v-else>暂无节点，请先新增节点。</div>
      <div style="margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap">
        <el-button
          type="primary"
          :disabled="!currentNode || submitLoading || isCompletedNodeReadonly || !isCurrentNodePromptConfigured"
          :loading="submitLoading"
          @click="runCurrentNode"
        >
          {{ primaryGenerateButtonLabel }}
        </el-button>
        <el-button
          :disabled="!currentNode || submitLoading || isCompletedNodeReadonly || !currentNodeHasCompletableOutput"
          @click="completeNode"
        >
          保存并下一步
        </el-button>
        <el-button :disabled="!currentNode || submitLoading" @click="resetToCurrentNode">重置到当前节点</el-button>
      </div>
    </el-card>

    <el-card v-if="isSceneDecompositionNode && currentNode?.sceneDecomposition" shadow="never" class="sd-panel">
      <div class="sd-ai-block">
        <div class="sd-ai-label">
          AI 辅助修改（输入 <code>/</code> 可搜索并选择「整表 / 某场景卡片」，再写说明后点「生成/重新生成」；选中后仅调用对应范围的接口）
        </div>
        <div v-loading="submitLoading" element-loading-text="正在请求大模型，请稍候…" class="sd-ai-inner sd-ai-inner--slash">
          <div
            ref="sdAiTextareaWrapRef"
            class="sd-ai-textarea-wrap sd-ai-composer-shell"
            :class="{ 'sd-ai-composer-shell--disabled': submitLoading || isCompletedNodeReadonly }"
          >
            <div class="sd-scope-chip-row">
              <div class="sd-scope-chip" :title="sceneDecompScopeTitle">
                <span class="sd-scope-chip-text">{{ sceneDecompScopeChipText }}</span>
                <button
                  v-if="sceneDecompAiTarget && !isCompletedNodeReadonly"
                  type="button"
                  class="sd-scope-chip-x"
                  aria-label="清除为整表范围"
                  @click="clearSceneDecompAiTarget"
                >
                  ×
                </button>
              </div>
            </div>
            <el-input
              ref="sdAiInputRef"
              v-model="currentNode.sceneDecomposition.aiModifyText"
              type="textarea"
              :rows="6"
              :disabled="submitLoading || isCompletedNodeReadonly"
              class="sd-ai-input-inside"
              placeholder="先按 / 选择范围（可选，不选则整表）；再写修改要求。↑↓ 选择菜单项，Enter 确认，Esc 关闭。"
              @keydown="onSdAiKeydown"
              @input="onSdAiInput"
            />
            <div
              v-show="sdSlashMenuVisible"
              class="sd-slash-menu"
              role="listbox"
              :style="sdSlashMenuStyle"
              @mousedown.prevent
            >
              <div
                v-for="(opt, oi) in sdSlashFilteredOptions"
                :key="opt.key"
                class="sd-slash-item"
                :class="{ 'is-active': oi === sdSlashHighlight }"
                role="option"
                @click="pickSdSlashOption(opt)"
              >
                {{ opt.label }}
              </div>
              <div v-if="!sdSlashFilteredOptions.length" class="sd-slash-empty">无匹配项</div>
            </div>
          </div>
          <div class="sd-ai-actions">
            <el-button
              type="primary"
              class="sd-ai-submit"
              :loading="submitLoading"
              :disabled="submitLoading || isCompletedNodeReadonly || !isCurrentNodePromptConfigured"
              @click="runSceneDecompositionAi"
            >
              {{ primaryGenerateButtonLabel }}
            </el-button>
            <el-button
              :disabled="submitLoading || isCompletedNodeReadonly || !currentNodeHasCompletableOutput"
              @click="completeNode"
            >
              保存并下一步
            </el-button>
            <el-button :disabled="submitLoading" @click="resetToCurrentNode">重置到当前节点</el-button>
          </div>
        </div>
      </div>

      <div v-if="!(currentNode.sceneDecomposition.scenes || []).length" class="sd-empty">
        <p>暂无场景卡片。点击「生成」可由模型根据上游故事拆解；或手动新建场景。</p>
        <el-button type="success" plain :disabled="isCompletedNodeReadonly" @click="createEmptySceneDecompScene">
          新建场景
        </el-button>
      </div>
      <div v-else class="sd-scene-list">
        <div v-for="(s, si) in currentNode.sceneDecomposition.scenes" :key="s.id" class="sd-scene-card">
          <template v-if="sceneDecompEditingId === s.id">
            <div class="sd-scene-head sd-scene-head--edit">
              <div class="sd-scene-edit-fields">
                <el-input
                  v-model="s.title"
                  :placeholder="`例如：场景${si + 1} · 深夜便利店门口`"
                  class="sd-scene-title-input"
                />
              </div>
              <el-button type="primary" size="small" :disabled="isCompletedNodeReadonly" @click="finishSceneDecompInlineEdit">
                完成
              </el-button>
            </div>
            <div class="sd-scene-edit-body">
              <el-input
                v-model="s.text"
                type="textarea"
                :autosize="{ minRows: 6, maxRows: 22 }"
                placeholder="本场景用一整段文字描述即可：空间、时间、人物、动作、情绪与视觉重点等均可写在一起。"
              />
            </div>
            <div class="sd-scene-footer">
              <span class="sd-scene-time">更新时间: {{ formatSdTime(s.updatedAt) }}</span>
            </div>
          </template>
          <template v-else>
            <div class="sd-scene-head">
              <span class="sd-scene-title">{{ s.title || '未命名场景' }}</span>
              <el-button type="success" size="small" plain :disabled="isCompletedNodeReadonly" @click="enterSceneDecompInlineEdit(s)">
                编辑
              </el-button>
            </div>
            <div class="sd-scene-body">{{ s.text?.trim() ? s.text : '—' }}</div>
            <div class="sd-scene-footer">
              <span class="sd-scene-time">更新时间: {{ formatSdTime(s.updatedAt) }}</span>
            </div>
          </template>
        </div>
      </div>
    </el-card>

    <el-card v-if="isFrameDecompositionNode && currentNode" shadow="never" class="fd-panel">
      <div class="fd-ai-block">
        <div class="fd-ai-label">
          AI 辅助修改（输入 <code>/</code> 可搜索并选择「整表 / 某场景 / 某画面」，再写说明后点「生成/重新生成」；选中后仅调用对应范围的接口）
        </div>
        <div v-loading="submitLoading" element-loading-text="正在请求大模型，请稍候…" class="fd-ai-inner fd-ai-inner--slash">
          <div
            ref="fdAiTextareaWrapRef"
            class="fd-ai-textarea-wrap fd-ai-composer-shell"
            :class="{ 'fd-ai-composer-shell--disabled': submitLoading || isCompletedNodeReadonly }"
          >
            <div class="fd-scope-chip-row">
              <div class="fd-scope-chip" :title="frameDecompScopeTitle">
                <span class="fd-scope-chip-text">{{ frameDecompScopeChipText }}</span>
                <button
                  v-if="frameDecompAiTarget && !isCompletedNodeReadonly"
                  type="button"
                  class="fd-scope-chip-x"
                  aria-label="清除为整表范围"
                  @click="clearFrameDecompAiTarget"
                >
                  ×
                </button>
              </div>
            </div>
            <el-input
              ref="fdAiInputRef"
              v-model="currentNode.frameDecomposition.aiModifyText"
              type="textarea"
              :rows="6"
              :disabled="submitLoading || isCompletedNodeReadonly"
              class="fd-ai-input-inside"
              placeholder="先按 / 选择范围（可选，不选则整表）；再写修改要求。↑↓ 选择菜单项，Enter 确认，Esc 关闭。"
              @keydown="onFdAiKeydown"
              @input="onFdAiInput"
            />
            <div
              v-show="fdSlashMenuVisible"
              class="fd-slash-menu"
              role="listbox"
              :style="fdSlashMenuStyle"
              @mousedown.prevent
            >
              <div
                v-for="(opt, oi) in fdSlashFilteredOptions"
                :key="opt.key"
                class="fd-slash-item"
                :class="{ 'is-active': oi === fdSlashHighlight }"
                role="option"
                @click="pickFdSlashOption(opt)"
              >
                {{ opt.label }}
              </div>
              <div v-if="!fdSlashFilteredOptions.length" class="fd-slash-empty">无匹配项</div>
            </div>
          </div>
          <div class="fd-ai-actions">
            <el-button
              type="primary"
              class="fd-ai-submit"
              :loading="submitLoading"
              :disabled="submitLoading || isCompletedNodeReadonly || !isCurrentNodePromptConfigured"
              @click="runFrameDecompositionAi"
            >
              {{ primaryGenerateButtonLabel }}
            </el-button>
            <el-button
              :disabled="submitLoading || isCompletedNodeReadonly || !currentNodeHasCompletableOutput"
              @click="completeNode"
            >
              保存并下一步
            </el-button>
            <el-button :disabled="submitLoading" @click="resetToCurrentNode">重置到当前节点</el-button>
          </div>
        </div>
      </div>

      <div v-if="!(currentNode.frameDecomposition.scenes || []).length" class="fd-empty">
        <p>
          暂无场景卡片。整表「生成」仅根据上一节点<strong>已定稿</strong>的场景稿（场景评审「修改后」）拆画面，不会用本节点旧 AI
          输出；也可手动新建场景。
        </p>
        <el-button type="success" plain :disabled="isCompletedNodeReadonly" @click="createEmptyFrameDecompScene">
          新建场景
        </el-button>
      </div>
      <div v-else class="fd-scene-list">
        <div v-for="s in currentNode.frameDecomposition.scenes" :key="s.id" class="fd-scene-card">
          <template v-if="frameDecompEditingId === s.id">
            <div class="fd-scene-head fd-scene-head--edit">
              <span class="fd-scene-title">{{ s.title || '未命名场景' }}</span>
              <el-button type="primary" size="small" :disabled="isCompletedNodeReadonly" @click="finishFrameDecompInlineEdit">
                完成
              </el-button>
            </div>
            <div class="fd-scene-desc-block" aria-readonly="true">
              <div class="fd-scene-desc-label">场景描述</div>
              <div class="fd-scene-desc-body">
                {{
                  getFrameDecompSceneDescription(s) ||
                  '（暂无上游场景正文，请结合标题编辑下方画面。）'
                }}
              </div>
            </div>
            <div class="fd-frames fd-frames--edit">
              <div v-for="(fr, fi) in s.frames" :key="fr.id" class="fd-frame-edit-row">
                <span class="fd-frame-label">画面{{ fi + 1 }}</span>
                <el-input
                  v-model="fr.description"
                  type="textarea"
                  :autosize="{ minRows: 2, maxRows: 12 }"
                  :disabled="isCompletedNodeReadonly"
                  placeholder="画面描述"
                />
                <el-button text type="danger" size="small" :disabled="isCompletedNodeReadonly" @click="removeFrameDecompRow(s, fi)">
                  删除
                </el-button>
              </div>
              <div v-if="!s.frames?.length" class="fd-frame-empty">点击下方添加画面</div>
              <el-button
                type="primary"
                plain
                size="small"
                class="fd-add-frame-btn"
                :disabled="isCompletedNodeReadonly"
                @click="addFrameDecompRow(s)"
              >
                添加画面
              </el-button>
            </div>
          </template>
          <template v-else>
            <div class="fd-scene-head">
              <span class="fd-scene-title">{{ s.title || '未命名场景' }}</span>
              <el-button type="success" size="small" plain :disabled="isCompletedNodeReadonly" @click="enterFrameDecompInlineEdit(s)">
                编辑
              </el-button>
            </div>
            <div class="fd-scene-desc-block" aria-readonly="true">
              <div class="fd-scene-desc-label">场景描述</div>
              <div class="fd-scene-desc-body">
                {{
                  getFrameDecompSceneDescription(s) ||
                  '（暂无上游场景正文，请结合标题编辑下方画面。）'
                }}
              </div>
            </div>
            <div class="fd-frames">
              <div v-for="(fr, fi) in s.frames" :key="fr.id" class="fd-frame-line">
                <span class="fd-frame-label">画面{{ fi + 1 }}:</span>
                <span class="fd-frame-text">{{ fr.description || '—' }}</span>
              </div>
              <div v-if="!s.frames?.length" class="fd-frame-empty">暂无画面描述</div>
            </div>
          </template>
          <div class="fd-scene-footer">
            <span class="fd-scene-time">更新时间: {{ formatFdTime(s.updatedAt) }}</span>
          </div>
        </div>
      </div>
    </el-card>

    <el-card v-if="isSceneReviewNode" shadow="never" class="output-card">
      <div class="output-card-header-row">
        <div style="font-weight: 600">输出</div>
        <el-button
          v-if="!sceneReviewRevising && sceneReviewView?.mode === 'parsed'"
          link
          type="primary"
          size="small"
          :disabled="isCompletedNodeReadonly"
          @click="enterSceneReviewEdit"
        >
          批量编辑
        </el-button>
      </div>
      <template v-if="sceneReviewView">
        <el-alert
          v-if="!sceneReviewView.upstreamPreview"
          type="warning"
          show-icon
          :closable="false"
          class="review-block-spacing"
          title="上一节点暂无输出"
          description="左侧「评审前」将没有可对齐的正文；生成评审时也无法附带上游内容。请先在「场景分解」等步骤生成输出。"
        />

        <template v-if="sceneReviewView.mode === 'parsed'">
          <div class="review-summary">
            <div class="review-summary-title">评审结果（模型返回）</div>
            <div v-if="sceneReviewView.data.conclusion" class="review-summary-conclusion">
              {{ sceneReviewView.data.conclusion }}
            </div>
            <div
              v-if="sceneReviewView.data.issueItems?.length || sceneReviewView.data.issues?.length"
              class="review-issue-checklist"
            >
              <div class="review-issue-checklist-title">【问题清单及修改建议】</div>
              <ul v-if="sceneReviewView.data.issueItems?.length" class="review-issue-pair-list">
                <li
                  v-for="(it, i) in sceneReviewView.data.issueItems"
                  :key="'sr-ii-' + i"
                  class="review-issue-pair-item"
                >
                  <div class="review-issue-line">
                    - {{ it.scene }}：{{ it.problem || '（见下方修改建议）' }}
                  </div>
                  <div v-if="it.suggestion" class="review-issue-line review-issue-line--sub">
                    - 修改建议：{{ it.suggestion }}
                  </div>
                </li>
              </ul>
              <ul v-else class="review-summary-issues">
                <li v-for="(item, i) in sceneReviewView.data.issues" :key="'sr-legacy-' + i">{{ item }}</li>
              </ul>
            </div>
          </div>
          <el-alert
            v-if="!sceneReviewView.data.original?.trim()"
            type="info"
            show-icon
            :closable="false"
            class="review-block-spacing"
            title="模型未在 JSON 中提供「原内容」"
            description="左侧「评审前」将直接回显上游正文并与「修改后」对比；结论与问题点仍来自模型。"
          />
          <el-alert
            v-if="!(sceneReviewView.data.revisedScenes?.length)"
            type="info"
            show-icon
            :closable="false"
            class="review-block-spacing"
            title="模型未输出有效的「修改后.scenes」"
            description="须为非空数组；可在编辑中补全或通过「重新生成该场景」生成。"
          />
          <div v-if="sceneReviewShowDiffLegend" class="review-diff-legend">
            <template v-if="!sceneReviewRevising">
              <span><span class="review-diff-legend-swatch review-diff-eq" />未改动</span>
              <span><span class="review-diff-legend-swatch review-diff-before" />评审前相对定稿删减（左栏浅红）</span>
              <span><span class="review-diff-legend-swatch review-diff-after" />定稿相对评审前新增（右栏浅绿）</span>
            </template>
            <template v-else>
              <span><span class="review-diff-legend-swatch review-diff-eq" />与打开编辑时一致</span>
              <span><span class="review-diff-legend-swatch review-diff-before" />相对打开编辑时删除（预览区「已删除」浅红）</span>
              <span><span class="review-diff-legend-swatch review-diff-after" />相对打开编辑时新增（预览区浅绿）</span>
            </template>
          </div>

          <template v-if="sceneReviewRevising && sceneReviewRevisedEditScenes.length">
            <div class="review-pane-head review-pane-head-row sr-scene-toolbar">
              <div>
                <strong>编辑修改后（按场景）</strong>
                <div class="review-pane-sub">保存后写入 JSON「修改后」的 scenes 结构</div>
              </div>
              <div class="review-pane-actions">
                <el-button size="small" @click="cancelSceneReviewEdit">取消</el-button>
                <el-button size="small" type="primary" :disabled="isCompletedNodeReadonly" @click="saveSceneReviewRevised">保存</el-button>
              </div>
            </div>
            <div
              v-for="(sc, si) in sceneReviewRevisedEditScenes"
              :key="sc.id"
              class="sr-edit-scene-card"
            >
              <div class="sr-edit-scene-label">场景 {{ si + 1 }}</div>
              <el-input
                v-model="sc.title"
                placeholder="场景标题（短一点）"
                :disabled="isCompletedNodeReadonly"
                class="sr-edit-title"
              />
              <el-input
                v-model="sc.text"
                type="textarea"
                :autosize="{ minRows: 4, maxRows: 16 }"
                :disabled="isCompletedNodeReadonly"
                placeholder="完整场景说明：地点、人物、冲突、画面重点等"
                spellcheck="false"
              />
            </div>
            <div class="review-session-diff-wrap">
              <div class="review-session-diff-title">变更高亮（相对进入本次编辑时）</div>
              <div v-if="sceneReviewSessionRemovalSpans.length" class="review-session-diff-block">
                <div class="review-session-diff-subtitle">已删除</div>
                <div class="review-diff-text review-session-diff-body">
                  <template v-for="(seg, di) in sceneReviewSessionRemovalSpans" :key="`sesl-${di}`">
                    <span :class="seg.op === 'before' ? 'review-diff-before' : 'review-diff-eq'">{{ seg.text }}</span>
                  </template>
                </div>
              </div>
              <div class="review-session-diff-block">
                <div class="review-session-diff-subtitle">当前稿</div>
                <div v-if="sceneReviewSessionDiff.right.length" class="review-diff-text review-session-diff-body">
                  <template v-for="(seg, di) in sceneReviewSessionDiff.right" :key="`ses-${di}`">
                    <span :class="seg.op === 'after' ? 'review-diff-after' : 'review-diff-eq'">{{ seg.text }}</span>
                  </template>
                </div>
                <pre v-else class="review-diff-empty review-session-diff-body">（空）</pre>
              </div>
            </div>
          </template>

          <template v-else>
            <el-alert
              v-if="sceneReviewUsedUpstreamAsDiffBase"
              type="info"
              show-icon
              :closable="false"
              class="review-block-spacing"
              title="评审前列表来自上游场景分解（模型未填「原内容」）"
            />
            <div
              v-for="row in sceneReviewPerSceneRows"
              :key="'sr-row-' + row.index"
              class="sr-per-scene-block"
            >
              <div class="sr-per-scene-title">
                场景 {{ row.index + 1
                }}<template v-if="row.sceneHeadline">：{{ row.sceneHeadline }}</template>
              </div>
              <div class="review-compare sr-per-scene-compare">
                <div class="review-pane">
                  <div class="review-pane-head"><div>评审前</div></div>
                  <div class="review-pane-body review-pane-body--diff">
                    <div v-if="row.diff.left.length" class="review-diff-text">
                      <template v-for="(seg, di) in row.diff.left" :key="'srpl-' + row.index + '-' + di">
                        <span :class="seg.op === 'before' ? 'review-diff-before' : 'review-diff-eq'">{{ seg.text }}</span>
                      </template>
                    </div>
                    <pre v-else class="review-diff-empty">（无）</pre>
                  </div>
                </div>
                <div class="review-pane">
                  <div class="review-pane-head review-pane-head-row">
                    <div>评审后</div>
                    <div class="sr-row-actions">
                      <template v-if="sceneReviewInlineEditIndex === row.index">
                        <el-button size="small" :disabled="isCompletedNodeReadonly" @click="cancelSceneReviewInlineEdit">
                          取消
                        </el-button>
                        <el-button
                          size="small"
                          type="primary"
                          :disabled="isCompletedNodeReadonly"
                          @click="saveSceneReviewInlineEdit"
                        >
                          保存
                        </el-button>
                      </template>
                      <el-button
                        v-else
                        size="small"
                        type="primary"
                        plain
                        :disabled="isCompletedNodeReadonly || sceneReviewInlineEditIndex !== null"
                        @click="startSceneReviewInlineEdit(row.index)"
                      >
                        编辑
                      </el-button>
                    </div>
                  </div>
                  <div class="review-pane-body review-pane-body--diff">
                    <template v-if="sceneReviewInlineEditIndex === row.index">
                      <el-input
                        v-model="sceneReviewInlineAfterDraft"
                        type="textarea"
                        :autosize="{ minRows: 8, maxRows: 28 }"
                        :disabled="isCompletedNodeReadonly"
                        class="sr-inline-after-input"
                        placeholder="编辑本场景正文（标题在上方「场景 N：…」展示）"
                        spellcheck="false"
                      />
                    </template>
                    <template v-else>
                      <div v-if="row.diff.right.length" class="review-diff-text">
                        <template v-for="(seg, di) in row.diff.right" :key="'srpr-' + row.index + '-' + di">
                          <span :class="seg.op === 'after' ? 'review-diff-after' : 'review-diff-eq'">{{ seg.text }}</span>
                        </template>
                      </div>
                      <pre v-else class="review-diff-empty">（无）</pre>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </template>

        <div v-else class="review-parse-fallback">
          <el-alert
            type="error"
            show-icon
            :closable="false"
            class="review-block-spacing"
            title="无法按场景评审格式解析模型输出"
            :description="sceneReviewView.failureReason || '未知原因'"
          />
          <div style="font-weight: 600; margin-top: 12px">模型原始输出（未改写）</div>
          <div class="review-fallback-text">{{ currentOutputText || '（空）' }}</div>
          <el-button size="small" class="review-fallback-copy" :disabled="!currentOutputText" @click="copyOutput">
            一键复制全文
          </el-button>
        </div>
      </template>
    </el-card>

    <el-card v-else-if="isFrameReviewNode" shadow="never" class="output-card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px">
        <div style="font-weight: 600">输出</div>
        <el-button size="small" :disabled="!currentOutputText" @click="copyOutput">一键复制原文 JSON</el-button>
      </div>
      <template v-if="frameReviewData">
        <div class="review-summary review-summary--frame">
          <div class="review-summary-title">评审结论</div>
          <div class="review-summary-conclusion">{{ frameReviewData.summary || '（无）' }}</div>
          <div
            v-if="frameReviewData.issueItems?.length || frameReviewData.merits?.length || frameReviewData.suggestions?.length"
            class="review-issue-checklist"
          >
            <div class="review-issue-checklist-title">【问题清单及修改建议】</div>
            <ul v-if="frameReviewData.issueItems?.length" class="review-issue-pair-list">
              <li
                v-for="(it, i) in frameReviewData.issueItems"
                :key="'fr-ii-' + i"
                class="review-issue-pair-item"
              >
                <div class="review-issue-line">
                  - {{ it.scene }}：{{ it.problem || '（见下方修改建议）' }}
                </div>
                <div v-if="it.suggestion" class="review-issue-line review-issue-line--sub">
                  - 修改建议：{{ it.suggestion }}
                </div>
              </li>
            </ul>
            <template v-else>
              <ul v-if="frameReviewData.merits?.length" class="review-summary-issues">
                <li v-for="(m, i) in frameReviewData.merits" :key="`fr-merit-${i}`">
                  <span class="fr-tag">优点</span>{{ m }}
                </li>
              </ul>
              <ul v-if="frameReviewData.suggestions?.length" class="review-summary-issues">
                <li v-for="(s, i) in frameReviewData.suggestions" :key="`fr-sug-${i}`">
                  <span class="fr-tag">建议</span>{{ s }}
                </li>
              </ul>
            </template>
          </div>
        </div>

        <el-alert
          v-if="!frameReviewDiffBasePlain.trim()"
          type="info"
          show-icon
          :closable="false"
          class="review-block-spacing"
          title="上一节点暂无输出"
          description="「修改前」无法与「修改后」对比；请先完成「画面分解」或在生成时在提示词中附带待评审分镜。"
        />

        <div v-if="frameReviewDiffHasBothSides || frameReviewRevising" class="review-diff-legend">
          <template v-if="!frameReviewRevising">
            <span><span class="review-diff-legend-swatch review-diff-eq" />未改动</span>
            <span><span class="review-diff-legend-swatch review-diff-before" />相对修改后有删减（左栏浅红）</span>
            <span><span class="review-diff-legend-swatch review-diff-after" />修改后新增（右栏浅绿）</span>
          </template>
          <template v-else>
            <span><span class="review-diff-legend-swatch review-diff-eq" />与打开编辑时一致</span>
            <span><span class="review-diff-legend-swatch review-diff-before" />相对打开编辑时删除（预览浅红）</span>
            <span><span class="review-diff-legend-swatch review-diff-after" />相对打开编辑时新增（预览浅绿）</span>
          </template>
        </div>

        <div class="review-compare" :class="{ 'review-compare--frame-editing': frameReviewRevising }">
          <div class="review-pane">
            <div class="review-pane-head">
              <div>修改前</div>
              <div v-if="frameReviewDiffBasePlain.trim()" class="review-diff-base-tag">与上游画面分解（格式化文本）对齐对比</div>
            </div>
            <div
              ref="reviewScrollLeftRef"
              class="review-pane-body review-pane-body--diff"
              @scroll="onReviewPaneScroll('left')"
            >
              <div v-if="frameReviewDiff.left.length" class="review-diff-text">
                <template v-for="(seg, di) in frameReviewDiff.left" :key="`frl-${di}`">
                  <span :class="seg.op === 'before' ? 'review-diff-before' : 'review-diff-eq'">{{ seg.text }}</span>
                </template>
              </div>
              <pre v-else class="review-diff-empty">（无）</pre>
            </div>
          </div>
          <div class="review-pane">
            <div class="review-pane-head review-pane-head-row">
              <div>
                <div>修改后</div>
                <div v-if="!frameReviewRevising" class="review-pane-sub">
                  右侧为对比稿；点「编辑」后按场景、画面分块修改描述（可增删画面）。若模型未返回「修改后」，编辑时会尝试用「画面分解」结果填充。
                </div>
                <div v-else class="review-pane-sub">编辑中；下方为相对打开编辑时的变更预览</div>
              </div>
              <div class="review-pane-actions">
                <template v-if="!frameReviewRevising">
                  <el-button size="small" type="primary" plain :disabled="isCompletedNodeReadonly" @click="enterFrameReviewEdit">
                    编辑
                  </el-button>
                  <el-button
                    size="small"
                    type="primary"
                    :disabled="!frameReviewDiffRevisedPlain.trim()"
                    @click="copyFrameReviewOptimizedPlain"
                  >
                    一键复制
                  </el-button>
                </template>
                <template v-else>
                  <el-button size="small" @click="cancelFrameReviewEdit">取消</el-button>
                  <el-button size="small" type="primary" :disabled="isCompletedNodeReadonly" @click="saveFrameReviewOptimized">
                    保存
                  </el-button>
                </template>
              </div>
            </div>
            <div
              ref="reviewScrollRightRef"
              class="review-pane-body review-pane-body--diff"
              :class="{ 'review-pane-body--edit-stack': frameReviewRevising }"
              @scroll="onReviewPaneScroll('right')"
            >
              <template v-if="!frameReviewRevising">
                <div v-if="frameReviewDiff.right.length" class="review-diff-text">
                  <template v-for="(seg, di) in frameReviewDiff.right" :key="`frr-${di}`">
                    <span :class="seg.op === 'after' ? 'review-diff-after' : 'review-diff-eq'">{{ seg.text }}</span>
                  </template>
                </div>
                <pre v-else class="review-diff-empty">（无）</pre>
              </template>
              <template v-else>
                <div v-if="!frameReviewOptimizedEditScenes.length" class="fr-opt-empty">
                  暂无可编辑的场景/画面：请完成模型生成且 JSON 中含「修改后」或「优化分镜」；若仅有评审文字，可先完成「画面分解」后点「编辑」，将自动从上游载入画面结构再改。
                </div>
                <div v-else class="fr-opt-modules">
                  <div
                    v-for="(sc, si) in frameReviewOptimizedEditScenes"
                    :key="`fr-opt-sc-${si}`"
                    class="fr-opt-scene-card"
                  >
                    <div class="fr-opt-scene-head">
                      <span class="fr-opt-scene-badge">场景 {{ si + 1 }}</span>
                      <el-input
                        v-model="sc.title"
                        placeholder="场景标题（可选，以画面编辑为主）"
                        class="fr-opt-scene-title-input"
                        :disabled="isCompletedNodeReadonly"
                      />
                      <el-button
                        v-if="!isCompletedNodeReadonly"
                        size="small"
                        type="primary"
                        link
                        @click="addFrameReviewShot(si)"
                      >
                        添加画面
                      </el-button>
                    </div>
                    <div class="fr-opt-frames">
                      <div
                        v-for="(fr, fi) in sc.frames"
                        :key="`fr-opt-f-${si}-${fi}`"
                        class="fr-opt-frame-block"
                      >
                        <div class="fr-opt-frame-row">
                          <div class="fr-opt-frame-label">画面 {{ fi + 1 }}</div>
                          <el-button
                            v-if="!isCompletedNodeReadonly && sc.frames.length > 1"
                            size="small"
                            type="danger"
                            link
                            @click="removeFrameReviewShot(si, fi)"
                          >
                            删除
                          </el-button>
                        </div>
                        <el-input
                          v-model="fr.description"
                          type="textarea"
                          :autosize="{ minRows: 3, maxRows: 18 }"
                          placeholder="画面描述（景别、主体、动作、光影等）"
                          class="fr-opt-frame-textarea"
                          :disabled="isCompletedNodeReadonly"
                          spellcheck="false"
                        />
                      </div>
                    </div>
                  </div>
                </div>
                <div class="review-session-diff-wrap">
                  <div class="review-session-diff-title">变更高亮（相对进入本次编辑时）</div>
                  <div v-if="frameReviewSessionRemovalSpans.length" class="review-session-diff-block">
                    <div class="review-session-diff-subtitle">已删除</div>
                    <div class="review-diff-text review-session-diff-body">
                      <template v-for="(seg, di) in frameReviewSessionRemovalSpans" :key="`frsesl-${di}`">
                        <span :class="seg.op === 'before' ? 'review-diff-before' : 'review-diff-eq'">{{ seg.text }}</span>
                      </template>
                    </div>
                  </div>
                  <div class="review-session-diff-block">
                    <div class="review-session-diff-subtitle">当前稿</div>
                    <div v-if="frameReviewSessionDiff.right.length" class="review-diff-text review-session-diff-body">
                      <template v-for="(seg, di) in frameReviewSessionDiff.right" :key="`frses-${di}`">
                        <span :class="seg.op === 'after' ? 'review-diff-after' : 'review-diff-eq'">{{ seg.text }}</span>
                      </template>
                    </div>
                    <pre v-else class="review-diff-empty review-session-diff-body">（空）</pre>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="review-parse-fallback">
        <el-alert
          type="info"
          show-icon
          :closable="false"
          title="未识别到结构化画面评审"
          description="请让模型只输出一段合法 JSON，且至少包含：评审结论（或总评 / conclusion）、以及修改后或优化分镜（scenes[].frames[].description）；仍支持优点、改进建议等旧字段。若仍失败，请检查 JSON 是否被说明文字截断或未转义。"
        />
        <div class="review-fallback-text">{{ currentOutputText || '暂无输出' }}</div>
        <el-button size="small" class="review-fallback-copy" :disabled="!currentOutputText" @click="copyOutput">一键复制全文</el-button>
      </div>
    </el-card>

    <template v-else-if="isFullContentGenNode && currentNode">
      <el-card shadow="never" class="fcg-input-card" style="margin-bottom: 12px">
        <div style="font-weight: 600; margin-bottom: 8px">按场景依次生成（漫画 / 动画提示词）</div>
        <p class="fcg-input-hint">
          点击「生成」会<strong>按场景逐个</strong>请求大模型：每场景只带该场景下各画面主述，成功后立即写入表格并<strong>保存到服务器</strong>；某一场景失败不影响已成功的场景。除模板与下方输入外，主题侧仅附带人物设定里以「角色长相」标出的段落（「角色长相：」或「【角色长相】」）。每轮模型须返回<strong>仅含 1 个场景</strong>的
          <code>version: 1</code> JSON（<code>scenes</code> 数组长度为 1，结构见下方折叠说明）。各格仍可用「编辑」手改。
        </p>
        <div style="position: relative; min-height: 100px">
          <el-input
            v-model="currentNode.inputText"
            type="textarea"
            :rows="4"
            :disabled="isCompletedNodeReadonly"
            placeholder="补充要求：如整体风格、对白密度、运镜偏好等（可选）"
          />
        </div>
        <div class="fcg-toolbar-row" style="margin-top: 12px">
          <el-button
            type="primary"
            :disabled="
              !currentNode || fullContentBatchRunning || isCompletedNodeReadonly || !isCurrentNodePromptConfigured
            "
            :loading="fullContentBatchRunning"
            @click="runCurrentNode"
          >
            {{ primaryGenerateButtonLabel }}
          </el-button>
          <el-button
            :disabled="isCompletedNodeReadonly || !currentNodeHasCompletableOutput"
            @click="completeNode"
          >
            完成
          </el-button>
          <el-button :disabled="fullContentBatchRunning" @click="resetToCurrentNode">重置到当前节点</el-button>
        </div>
      </el-card>

      <el-card v-if="currentNode.fullContentGen" shadow="never" class="fcg-main-card">
        <div class="fcg-hero">
          <div class="fcg-hero-row">
            <span class="fcg-hero-label">主题名称</span>
            <span class="fcg-hero-value">{{ currentNode.fullContentGen.themeName || '—' }}</span>
          </div>
          <div class="fcg-hero-row">
            <span class="fcg-hero-label">分镜名称</span>
            <span class="fcg-hero-value">{{ currentNode.fullContentGen.boardName || '—' }}</span>
          </div>
          <div class="fcg-story-block">
            <div class="fcg-block-title">故事描述</div>
            <div class="fcg-story-body">{{ currentNode.fullContentGen.storyText?.trim() || '（暂无，请完成「故事描述」节点）' }}</div>
          </div>
        </div>

        <el-collapse v-if="currentNode.fullContentGen.scenes?.length" class="fcg-format-collapse">
          <el-collapse-item title="复制到「提示词管理」：分批 JSON 格式说明（version 1）" name="fcg-json">
            <div class="fcg-format-hint">
              <p class="fcg-format-p">
                将下方<strong>整段</strong>复制到模板<strong>正文</strong>或<strong>输出格式示例</strong>；模板响应格式建议选
                <strong>JSON</strong>。生成时系统<strong>按场景多次</strong>请求，每次用户消息只含<strong>一个场景</strong>的画面主述；模型每次须返回
                <strong>scenes 长度为 1</strong> 的一段合法 JSON，不要用 markdown 代码块。
              </p>
              <el-button type="primary" plain size="small" class="fcg-copy-spec-btn" @click="copyFullContentPromptSpecForConfig">
                复制格式说明全文
              </el-button>
              <pre class="fcg-format-pre">{{ fullContentBatchJsonFormatExample }}</pre>
              <p class="fcg-format-p fcg-format-note">
                单次响应：<code>scenes</code> 仅 1 项；其下 <code>shots</code> 顺序 = 该场景画面1、2…。<code>comicDesc</code> /
                <code>animDesc</code> 为漫画、动画提示词；可用别名 <code>comic</code>、<code>anim</code>、<code>animation</code>。<code>shotText</code>
                可与表内主述一致或略写；顶栏字段可省略。下方示例为「全表」结构，实际每次只须输出其中一段场景。
              </p>
            </div>
          </el-collapse-item>
        </el-collapse>

        <div v-if="!currentNode.fullContentGen.scenes?.length" class="fcg-empty">
          暂无场景/画面数据。请先完成「画面评审」（或「画面分解」）等上游步骤；进入本节点时会自动从流水线拉取结构与画面主述。
        </div>
        <div v-else class="fcg-scene-list">
          <div
            v-for="(sc, si) in currentNode.fullContentGen.scenes"
            :key="sc.id"
            v-loading="fullContentSceneLoadingSi === si"
            element-loading-text="正在生成本场景提示词…"
            class="fcg-scene-card fcg-scene-card--loading-host"
          >
            <div class="fcg-scene-head">
              <span class="fcg-scene-title">
                【场景{{ si + 1 }}：{{ stripLeadingSceneIndexForFcg(sc.title, si + 1) || '未命名场景' }}】
              </span>
              <el-button
                type="primary"
                plain
                size="small"
                class="fcg-scene-regen-btn"
                :loading="fullContentSceneLoadingSi === si"
                :disabled="
                  isCompletedNodeReadonly ||
                  !isCurrentNodePromptConfigured ||
                  fullContentBatchRunning ||
                  (fullContentSceneLoadingSi !== -1 && fullContentSceneLoadingSi !== si)
                "
                @click="regenerateFullContentScene(si)"
              >
                重新生成
              </el-button>
            </div>
            <div v-if="sc.sceneText?.trim()" class="fcg-scene-desc">
              <span class="fcg-inline-label">场景说明</span>
              <div class="fcg-scene-desc-body">{{ sc.sceneText.trim() }}</div>
            </div>
            <div class="fcg-scene-shots">
              <div class="fcg-scene-shots-label">
                分镜画面（主述只读；漫画 / 动画可「编辑」，或标题栏「重新生成」只重跑本场景；上方「生成」为按顺序跑全部场景）
              </div>
              <div v-for="(sh, fi) in sc.shots" :key="sh.id" class="fcg-shot-card">
                <div class="fcg-shot-lead">
                  <span class="fcg-shot-bullet">·</span>
                  <span class="fcg-shot-line-label">画面{{ fi + 1 }}：</span>
                  <div class="fcg-shot-line-body">{{ sh.shotText?.trim() || '（暂无画面主述，请检查上游画面评审/画面分解）' }}</div>
                  <div class="fcg-shot-lead-actions">
                    <el-button size="small" text @click="copyFullContentField(sh.shotText)">复制</el-button>
                  </div>
                </div>
                <div class="fcg-shot-prompts-label">提示词（漫画 / 动画：仅手动编辑）</div>
                <div class="fcg-shot-cols">
                  <div class="fcg-shot-col">
                    <div class="fcg-shot-col-head">
                      <span>漫画提示词</span>
                      <span class="fcg-shot-actions">
                        <el-button
                          size="small"
                          text
                          type="primary"
                          :disabled="isCompletedNodeReadonly || fullContentSceneLoadingSi === si"
                          @click="openFullContentEdit(si, fi, 'comic')"
                        >
                          编辑
                        </el-button>
                        <el-button size="small" text @click="copyFullContentField(sh.comicDesc)">复制</el-button>
                      </span>
                    </div>
                    <div class="fcg-shot-text">{{ sh.comicDesc?.trim() || '（空）' }}</div>
                  </div>
                  <div class="fcg-shot-col">
                    <div class="fcg-shot-col-head">
                      <span>动画提示词</span>
                      <span class="fcg-shot-actions">
                        <el-button
                          size="small"
                          text
                          type="primary"
                          :disabled="isCompletedNodeReadonly || fullContentSceneLoadingSi === si"
                          @click="openFullContentEdit(si, fi, 'anim')"
                        >
                          编辑
                        </el-button>
                        <el-button size="small" text @click="copyFullContentField(sh.animDesc)">复制</el-button>
                      </span>
                    </div>
                    <div class="fcg-shot-text">{{ sh.animDesc?.trim() || '（空）' }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-card>
      <el-card v-else shadow="never" class="fcg-main-card fcg-main-card--pending">
        <div class="fcg-pending">正在准备完整内容，请稍候…</div>
      </el-card>
    </template>

    <el-card v-else-if="isStoryDescriptionNode" shadow="never" class="output-card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
        <div style="font-weight: 600">输出</div>
        <el-button size="small" :disabled="!currentOutputText" @click="copyOutput">一键复制原文</el-button>
      </div>
      <div class="story-out-body">{{ storyDescriptionDisplayText }}</div>
    </el-card>

    <el-card v-else-if="!isFrameDecompositionNode && !isSceneDecompositionNode && !isFullContentGenNode" shadow="never" class="output-card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
        <div style="font-weight: 600">输出</div>
        <el-button size="small" :disabled="!currentOutputText" @click="copyOutput">一键复制</el-button>
      </div>
      <div style="white-space: pre-wrap; min-height: 90px">{{ currentOutputText || '暂无输出' }}</div>
    </el-card>

    <el-card v-if="!isFrameDecompositionNode && !isSceneDecompositionNode && !isFullContentGenNode" shadow="never" style="margin-top: 12px">
      <div style="font-weight: 600; margin-bottom: 8px">节点提示词（来自配置）</div>
      <el-input :model-value="storyboardPromptPreviewText" type="textarea" :rows="8" readonly />
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

  <el-dialog
    v-model="fullContentEditOpen"
    :title="fullContentEditDialogTitle"
    width="560px"
    destroy-on-close
    @closed="fullContentEditDraft = ''"
  >
    <el-input v-model="fullContentEditDraft" type="textarea" :rows="10" :placeholder="fullContentEditPlaceholder" />
    <template #footer>
      <el-button @click="fullContentEditOpen = false">取消</el-button>
      <el-button type="primary" @click="saveFullContentEdit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, unref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Sortable from 'sortablejs'
import DiffMatchPatch from 'diff-match-patch'
import http from '../api/http'

const route = useRoute()
const router = useRouter()
const sceneId = Number(route.params.id)
const scene = ref(null)
/** 运行页调试：切换节点仅拉 pipeline-node；需完整三路时可调用 fetchAiRunDiagnostics({ full: true }) */
const aiRunDiagnostics = ref(null)
const submitLoading = ref(false)
/** 完整内容：整批生成进行中（仅用于「生成」按钮 loading/防重复点击，不锁全页） */
const fullContentBatchRunning = ref(false)
/** 完整内容：当前正在请求的场景下标，-1 表示无；用于场景卡片局部 v-loading */
const fullContentSceneLoadingSi = ref(-1)
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
    {
      id: `node-${t}-2`,
      name: '场景分解',
      inputText: '',
      outputText: '',
      completed: false,
      enabled: true,
      modelId: null,
      promptId: null,
      sceneDecomposition: { filterModule: 'all', aiModifyText: '', scenes: [] },
    },
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
    {
      id: `node-${t}-6`,
      name: '完整内容生成',
      inputText: '',
      outputText: '',
      completed: false,
      enabled: true,
      modelId: null,
      promptId: null,
      fullContentGen: null,
      fullContentAiModifyText: '',
      fullContentAiTarget: null,
    },
  ]
}

const currentNode = computed(() => nodes.value[activeNodeIndex.value] || null)

/** 已启用的 LLM 配置（与后端仅调用 enabled 模型一致） */
const enabledLlmList = computed(() => (models.value || []).filter((m) => m.enabled !== false))

/** 发起分镜 AI 前校验：节点指定模型须存在且启用；未指定时须至少有一条已启用模型 */
const assertStoryboardLlmReady = (opts = {}) => {
  const silent = !!opts.silent
  const n = currentNode.value
  const mid = n?.modelId ?? null
  if (mid != null) {
    const row = (models.value || []).find((m) => m.id === mid)
    if (!row) {
      if (!silent) {
        ElMessage.error('当前节点绑定的模型已不存在。请打开「自定义节点」重新选择「LLM 配置」中的模型。')
      }
      return false
    }
    if (row.enabled === false) {
      if (!silent) {
        ElMessage.error('当前节点绑定的模型已禁用。请在「LLM 配置」中启用该模型，或更换为已启用的模型。')
      }
      return false
    }
    return true
  }
  if (!enabledLlmList.value.length) {
    if (!silent) {
      ElMessage.error('请先在「LLM 配置」中添加并启用至少一个模型，再使用 AI 分镜生成。')
    }
    return false
  }
  return true
}

/** 与后端 prompt_compose.compose_prompt_template_body 对齐：正文 + 返回格式 + 格式示例 */
const PROMPT_FORMAT_INTRO = {
  json: '【输出格式】只输出一段合法 JSON（禁止 markdown 代码块、禁止 JSON 前后的说明文字）。结构必须与下方「格式示例」的键名与层次完全一致；字符串内双引号须转义为 \\" 。',
  markdown: '【输出格式】使用 Markdown；标题层级、列表等请与下方「格式示例」保持一致。',
  text: '【输出格式】输出纯文本；分段与语气可参考下方「格式示例」（示例仅为结构参考，正文由你根据任务生成）。',
}

const normalizePromptResponseFormat = (v) => {
  const x = String(v || 'text').toLowerCase()
  return x === 'json' || x === 'markdown' || x === 'text' ? x : 'text'
}

const composePromptTemplateForLlm = (row) => {
  if (!row) return ''
  const main = String(row.description ?? '').trim()
  const fmt = normalizePromptResponseFormat(row.response_format)
  const example = String(row.format_example ?? '').trim()
  const parts = []
  if (main) parts.push(main)
  const intro = PROMPT_FORMAT_INTRO[fmt] || PROMPT_FORMAT_INTRO.text
  if (example) parts.push(`${intro}\n${example}`)
  else if (fmt !== 'text') parts.push(`${intro}\n（未配置格式示例时仍须严格遵守 ${fmt} 格式输出。）`)
  return parts.join('\n\n').trim()
}

/** AI 分镜：系统侧不再内置默认任务说明，须从「提示词管理」模板读取 */
const assertCurrentNodePromptConfigured = (opts = {}) => {
  const silent = !!opts.silent
  const n = currentNode.value
  if (!n) {
    if (!silent) ElMessage.error('当前无有效节点。')
    return false
  }
  if (!n.promptId) {
    if (!silent) ElMessage.error('请先在「自定义节点」中为当前节点选择提示词模板。')
    return false
  }
  const row = prompts.value.find((p) => p.id === n.promptId)
  if (!row) {
    if (!silent) ElMessage.error('所选提示词模板已不存在，请重新在「自定义节点」中选择。')
    return false
  }
  if (!String(composePromptTemplateForLlm(row) || '').trim()) {
    if (!silent) ElMessage.error('所选提示词模板正文或格式示例为空，请先在「提示词管理」中编辑该模板。')
    return false
  }
  return true
}

const isCurrentNodePromptConfigured = computed(() => {
  const n = currentNode.value
  if (!n?.promptId) return false
  const row = prompts.value.find((p) => p.id === n.promptId)
  return !!row && !!String(composePromptTemplateForLlm(row) || '').trim()
})

const defaultPromptText = computed(() => {
  if (!currentNode.value?.promptId) return ''
  const promptRow = prompts.value.find((item) => item.id === currentNode.value.promptId)
  if (!promptRow) return ''
  return composePromptTemplateForLlm(promptRow)
})

const storyboardPromptPreviewText = computed(() => {
  const t = String(defaultPromptText.value || '').trim()
  if (t) return t
  return '当前节点未配置有效提示词：请在「自定义节点」中为该节点选择模板，并在「提示词管理」中维护模板正文或格式示例。'
})

const currentOutputText = computed(() => currentNode.value?.outputText ?? '')

/** 已完成节点：仅可查看与复制，「重置到当前节点」后可再编辑 */
const isCompletedNodeReadonly = computed(() => !!currentNode.value?.completed)

/** 主「生成」按钮：尚无输出时为「生成」，已有输出后为「重新生成」 */
const primaryGenerateButtonLabel = computed(() =>
  String(currentNode.value?.outputText ?? '').trim() ? '重新生成' : '生成',
)

/** 「保存并下一步」前提：本节点 outputText 非空（结构化节点会在 complete 前同步） */
const currentNodeHasCompletableOutput = computed(() => !!String(currentNode.value?.outputText ?? '').trim())

const isSceneReviewNode = computed(() => currentNode.value?.name === '场景评审')
const isStoryDescriptionNode = computed(() => currentNode.value?.name === '故事描述')
const isFrameReviewNode = computed(() => currentNode.value?.name === '画面评审')
const isSceneDecompositionNode = computed(() => currentNode.value?.name === '场景分解')
const isFrameDecompositionNode = computed(() => currentNode.value?.name === '画面分解')
const isFullContentGenNode = computed(() => currentNode.value?.name === '完整内容生成')

/**
 * 从模型输出中提取第一个完整顶层 JSON 对象子串。
 * 不用 /\\{[\\s\\S]*\\}/：遇「修改后」等字段内嵌 JSON 字符串含 `}`、或正文后紧跟说明时，会吞到错误位置导致 JSON.parse 报 trailing content。
 */
const extractJsonObjectString = (raw) => {
  if (!raw || !String(raw).trim()) return null
  let text = String(raw).trim()
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i)
  if (fence) text = fence[1].trim()

  const start = text.indexOf('{')
  if (start < 0) return null

  let depth = 0
  let inString = false
  let escapeNext = false
  for (let i = start; i < text.length; i++) {
    const c = text[i]
    if (inString) {
      if (escapeNext) {
        escapeNext = false
        continue
      }
      if (c === '\\') {
        escapeNext = true
        continue
      }
      if (c === '"') {
        inString = false
        continue
      }
      continue
    }
    if (c === '"') {
      inString = true
      continue
    }
    if (c === '{') depth += 1
    else if (c === '}') {
      depth -= 1
      if (depth === 0) return text.slice(start, i + 1)
    }
  }
  return null
}

/** 画面评审等：括号扫描失败时尝试整段合法 JSON（模型输出含复杂转义时易误判边界） */
const extractStructuredJsonBlob = (raw) => {
  const sliced = extractJsonObjectString(raw)
  if (sliced) return sliced
  let text = String(raw ?? '').trim().replace(/^\uFEFF/, '')
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i)
  if (fence) text = fence[1].trim().replace(/^\uFEFF/, '')
  const t = text.trim()
  if (t.startsWith('{') && t.endsWith('}')) {
    try {
      JSON.parse(t)
      return t
    } catch {
      /* noop */
    }
  }
  if (t.startsWith('[') && t.endsWith(']')) {
    try {
      JSON.parse(t)
      return t
    } catch {
      /* noop */
    }
  }
  return null
}

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
  const sceneText =
    rawScene?.text ??
    rawScene?.正文 ??
    rawScene?.场景描述 ??
    rawScene?.summary ??
    rawScene?.sceneText ??
    ''
  return {
    id: rawScene?.id || `fd-s-${si}-${Date.now()}`,
    title: String(title),
    /** 模型若在场景级附带正文，用于只读展示（输出同步时可保留） */
    sceneText: String(sceneText || '').trim(),
    frames,
    updatedAt: rawScene?.updatedAt || new Date().toISOString(),
  }
}

const parseFrameDecompositionJson = (raw) => {
  const text = extractJsonObjectString(raw)
  if (!text) return null
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

/** 服务端/旧版本地状态可能只有空对象或缺 scenes，会导致既不初始化也不渲染 */
const frameDecompositionNeedsInit = (fd) => {
  if (fd == null || typeof fd !== 'object' || Array.isArray(fd)) return true
  if (!Array.isArray(fd.scenes)) return true
  return false
}

const syncFrameDecompToOutput = (node) => {
  if (!node?.frameDecomposition) return
  try {
    node.outputText = JSON.stringify({ scenes: node.frameDecomposition.scenes }, null, 2)
  } catch {
    node.outputText = ''
  }
}

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

const formatSdTime = formatFdTime

const legacySdFieldsToText = (raw) => {
  const loc = raw?.location ?? raw?.地点
  const tim = raw?.time ?? raw?.时间
  const ch = raw?.characters ?? raw?.人物 ?? raw?.出场人物
  const cf = raw?.conflict ?? raw?.冲突 ?? raw?.冲突点
  const vf = raw?.visualFocus ?? raw?.视觉 ?? raw?.视觉重点
  const lines = []
  if (loc) lines.push(`地点：${loc}`)
  if (tim) lines.push(`时间：${tim}`)
  if (ch) lines.push(`人物：${ch}`)
  if (cf) lines.push(`冲突：${cf}`)
  if (vf) lines.push(`视觉重点：${vf}`)
  return lines.join('\n')
}

const normalizeSdScene = (rawScene, si) => {
  const title = rawScene?.title ?? rawScene?.标题 ?? rawScene?.name ?? `场景${si + 1}`
  let text =
    rawScene?.text ??
    rawScene?.正文 ??
    rawScene?.content ??
    rawScene?.body ??
    rawScene?.description ??
    rawScene?.描述 ??
    ''
  text = String(text)
  if (!text.trim()) text = legacySdFieldsToText(rawScene)
  return {
    id: rawScene?.id || `sd-s-${si}-${Date.now()}`,
    title: String(title),
    text,
    updatedAt: rawScene?.updatedAt || new Date().toISOString(),
  }
}

const parseSceneDecompositionJson = (raw) => {
  const text = extractJsonObjectString(raw)
  if (!text) return null
  try {
    const o = JSON.parse(text)
    if (!o || typeof o !== 'object') return null
    let list = o.scenes ?? o.场景列表 ?? o.data
    if (!Array.isArray(list)) return null
    const scenes = list.map((rawScene, si) => normalizeSdScene(rawScene, si))
    if (!scenes.length) return null
    return { scenes }
  } catch {
    return null
  }
}

/**
 * 解析「【标题】\\n正文」块（与 formatReviewPanePlainText 输出的场景条一致）。
 */
const parseSceneBracketBlocks = (raw) => {
  const str = String(raw ?? '').trim()
  if (!str || !str.includes('【')) return null
  const chunks = str.split(/(?=【[^】]+】)/).filter((c) => c.trim())
  if (!chunks.length) return null
  const out = []
  for (const chunk of chunks) {
    const c = chunk.trim()
    const m = c.match(/^【([^】]+)】\s*\r?\n([\s\S]*)$/)
    if (m) out.push({ title: m[1].trim(), text: (m[2] || '').trim() })
    else {
      const m2 = c.match(/^【([^】]+)】\s*([\s\S]*)$/s)
      if (m2) out.push({ title: m2[1].trim(), text: (m2[2] || '').trim() })
      else out.push({ title: `场景${out.length + 1}`, text: c })
    }
  }
  return out.length ? out : null
}

const emptySceneDecomposition = () => ({
  filterModule: 'all',
  aiModifyText: '',
  scenes: [],
})

const syncSceneDecompToOutput = (node) => {
  if (!node?.sceneDecomposition) return
  try {
    const slim = node.sceneDecomposition.scenes.map((s) => ({
      id: s.id,
      title: s.title,
      text: String(s.text ?? ''),
      updatedAt: s.updatedAt,
    }))
    node.outputText = JSON.stringify({ scenes: slim }, null, 2)
  } catch {
    node.outputText = ''
  }
}

const sceneDecompNeedsNormalize = (scenes) => {
  if (!Array.isArray(scenes)) return false
  return scenes.some(
    (s) =>
      typeof s?.text !== 'string' ||
      'location' in (s || {}) ||
      'time' in (s || {}) ||
      'characters' in (s || {}) ||
      'conflict' in (s || {}) ||
      'visualFocus' in (s || {}),
  )
}

const ensureSceneDecompositionState = (node) => {
  if (!node || node.name !== '场景分解') return
  if (!node.sceneDecomposition) {
    const parsed = parseSceneDecompositionJson(node.outputText)
    node.sceneDecomposition = emptySceneDecomposition()
    if (parsed?.scenes?.length) {
      node.sceneDecomposition.scenes = parsed.scenes
    }
  } else if (sceneDecompNeedsNormalize(node.sceneDecomposition.scenes)) {
    node.sceneDecomposition.scenes = node.sceneDecomposition.scenes.map((s, si) => normalizeSdScene(s, si))
    syncSceneDecompToOutput(node)
    persistState()
  }
}

const getImmediateUpstreamOutput = () => {
  const idx = activeNodeIndex.value
  for (let i = idx - 1; i >= 0; i--) {
    const n = nodes.value[i]
    if (n.enabled === false) continue
    const t = n.outputText?.trim()
    if (t) return { name: n.name, text: t }
  }
  return null
}

/**
 * 画面分解整表生成专用：只投喂上一节点「已定稿」的场景稿，不把场景评审整段 JSON（结论/问题清单/原内容等）
 * 或本节点已生成的画面 JSON 混进请求。
 * - 场景评审：仅「修改后」的 scenes（title + text）序列化，与场景分解同构
 * - 场景分解等：沿用该节点 outputText（本身已是 { scenes: [...] }）
 */
const getUpstreamPayloadTextForFrameDecomposition = () => {
  const up = getImmediateUpstreamOutput()
  if (!up?.text?.trim()) return null

  if (up.name === '场景评审') {
    const pr = tryParseSceneReviewJson(up.text)
    if (pr.ok && pr.data.revisedScenes?.length) {
      const slim = pr.data.revisedScenes.map((sc, i) => ({
        title: String(sc.title || '').trim() || `场景${i + 1}`,
        text: String(sc.text ?? ''),
      }))
      return {
        name: up.name,
        text: JSON.stringify({ scenes: slim }, null, 2),
      }
    }
    const rev = pr.ok ? String(pr.data.revised || '').trim() : ''
    if (rev) {
      const parsed = parseSceneDecompositionJson(rev)
      if (parsed?.scenes?.length) {
        const slim = parsed.scenes.map((sc, i) => ({
          title: String(sc.title || '').trim() || `场景${i + 1}`,
          text: String(sc.text ?? ''),
        }))
        return { name: up.name, text: JSON.stringify({ scenes: slim }, null, 2) }
      }
    }
  }

  return { name: up.name, text: up.text }
}

const ensureFrameDecompositionState = (node) => {
  if (!node || node.name !== '画面分解') return
  const parsed = parseFrameDecompositionJson(node.outputText)
  if (frameDecompositionNeedsInit(node.frameDecomposition)) {
    node.frameDecomposition = emptyFrameDecomposition()
    if (parsed?.scenes?.length) {
      node.frameDecomposition.scenes = parsed.scenes
    }
    return
  }
  const fd = node.frameDecomposition
  if (fd.filterModule === undefined || fd.filterModule === null) fd.filterModule = 'all'
  if (fd.aiModifyText === undefined) fd.aiModifyText = ''
  if (!(fd.scenes || []).length && parsed?.scenes?.length) {
    fd.scenes = parsed.scenes
  }
}

watch(
  () => [activeNodeIndex.value, nodes.value],
  () => {
    const n = currentNode.value
    if (n?.name === '画面分解') ensureFrameDecompositionState(n)
    if (n?.name === '场景分解') ensureSceneDecompositionState(n)
  },
  { deep: true, immediate: true },
)

watch(isFrameDecompositionNode, (v) => {
  if (!v) {
    closeFdSlashMenu()
    clearFrameDecompAiTarget()
  }
})

const runSceneDecompositionAi = async () => {
  if (!currentNode.value || currentNode.value.name !== '场景分解') return
  if (isCompletedNodeReadonly.value) return
  if (!assertStoryboardLlmReady()) return
  if (!assertCurrentNodePromptConfigured()) return
  ensureSceneDecompositionState(currentNode.value)
  const sd = currentNode.value.sceneDecomposition
  const userPart = sd.aiModifyText?.trim() || ''
  const up = getImmediateUpstreamOutput()
  const target = sceneDecompAiTarget.value

  const handleSdAiError = (e) => {
    const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(String(e?.message || ''))
    if (isTimeout) {
      ElMessage.error('请求超时（大模型响应较慢）。若网络正常可稍后重试。')
      return
    }
    const d = e?.response?.data?.detail
    const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg || x).join('; ') : '生成失败'
    ElMessage.error(msg)
  }

  if (target?.type === 'scene') {
    const sceneRow = sd.scenes.find((x) => x.id === target.sceneId)
    if (!sceneRow) {
      ElMessage.warning('找不到该场景')
      return
    }
    const upstreamOk = !!up?.text?.trim()
    const hasLocal = String(sceneRow.text || '').trim().length > 0
    if (!upstreamOk && !hasLocal && !userPart) {
      ElMessage.warning('请先完成上游节点输出，或填写该场景正文 / 补充说明后再试')
      return
    }
    const bodyCore = buildSingleSceneCardDecompPrompt(sceneRow, sd)
    const upstreamCtx = up ? `\n【上一节点「${up.name}」输出】\n${up.text}` : ''
    const defaultText = [defaultPromptText.value, upstreamCtx, bodyCore].filter(Boolean).join('\n\n')
    submitLoading.value = true
    try {
      const { data } = await http.post(
        resolveAiPostUrl(null, 'single-scene-card-decomposition'),
        buildAiRunBody(defaultText, userPart, currentNode.value.modelId ?? null),
        { timeout: 300000 },
      )
      const out = modelOutputRaw(data)
      let merged = false
      if (data.parse_ok && data.scene) {
        sceneRow.title = String(data.scene.title || '').trim() || sceneRow.title
        sceneRow.text = String(data.scene.text ?? '')
        sceneRow.updatedAt = new Date().toISOString()
        merged = true
      }
      if (!merged) {
        const parsed = parseSceneDecompositionJson(out)
        if (parsed?.scenes?.length === 1) {
          const one = parsed.scenes[0]
          sceneRow.title = String(one.title || '').trim() || sceneRow.title
          sceneRow.text = String(one.text ?? '')
          sceneRow.updatedAt = new Date().toISOString()
          merged = true
        }
      }
      if (!merged) {
        ElMessage.warning('模型未返回单场景 JSON（scenes 长度须为 1），请调整说明后重试')
        return
      }
      currentNode.value.outputText = out
      sd.aiModifyText = ''
      clearSceneDecompAiTarget()
      closeSdSlashMenu()
      syncSceneDecompToOutput(currentNode.value)
      await persistPipelineAfterGenerate()
      ElMessage.success('已更新该场景卡片')
    } catch (e) {
      handleSdAiError(e)
    } finally {
      submitLoading.value = false
    }
    return
  }

  const upstreamCtx = up ? `\n【上一节点「${up.name}」输出】\n${up.text}` : ''
  const scenesCtx =
    sd.scenes?.length > 0
      ? `\n当前场景分解数据（请按需修改后输出完整 JSON）：\n${JSON.stringify({ scenes: sd.scenes }, null, 2)}`
      : ''
  const defaultText = [defaultPromptText.value, upstreamCtx, scenesCtx].filter(Boolean).join('\n\n')
  const hasUpstream = !!upstreamCtx
  const hasScenes = sd.scenes?.length > 0
  if (!hasUpstream && !hasScenes && !userPart) {
    ElMessage.warning('请先完成上游节点输出，或填写说明 / 新建场景后再提交')
    return
  }
  submitLoading.value = true
  try {
    const { data } = await http.post(
      resolveAiPostUrl('场景分解'),
      buildAiRunBody(defaultText, userPart || '', currentNode.value.modelId ?? null),
      { timeout: 300000 },
    )
    const out = modelOutputRaw(data)
    let applied = false
    if (data.parse_ok && Array.isArray(data.scenes) && data.scenes.length) {
      sd.scenes = data.scenes.map((s, i) => ({
        title: String(s.title || '').trim() || `场景${i + 1}`,
        text: String(s.text || ''),
        updatedAt: new Date().toISOString(),
        id: `sd-s-${i}-${Date.now()}`,
      }))
      applied = true
    }
    const parsed = applied ? { scenes: sd.scenes } : parseSceneDecompositionJson(out)
    if (parsed?.scenes?.length) {
      if (!applied) {
        sd.scenes = parsed.scenes.map((s, i) => ({
          ...s,
          updatedAt: new Date().toISOString(),
          id: s.id || `sd-s-${i}-${Date.now()}`,
        }))
      }
      sd.filterModule = 'all'
      currentNode.value.outputText = out
      sd.aiModifyText = ''
      clearSceneDecompAiTarget()
      closeSdSlashMenu()
      await persistPipelineAfterGenerate()
      ElMessage.success('已更新场景卡片')
    } else {
      ElMessage.warning('模型未返回可解析的 JSON（需包含 scenes 数组），请调整说明后重试')
    }
  } catch (e) {
    handleSdAiError(e)
  } finally {
    submitLoading.value = false
  }
}

/** 场景分解：当前内联编辑中的场景 id（无弹窗） */
const sceneDecompEditingId = ref(null)

const normalizeSceneDecompSceneById = (sd, id) => {
  if (!sd?.scenes || !id) return false
  const idx = sd.scenes.findIndex((s) => s.id === id)
  if (idx < 0) return false
  const s = sd.scenes[idx]
  s.title = String(s.title || '').trim() || `场景${idx + 1}`
  s.text = String(s.text ?? '')
  s.updatedAt = new Date().toISOString()
  return true
}

const enterSceneDecompInlineEdit = (sceneRow) => {
  if (isCompletedNodeReadonly.value) return
  ensureSceneDecompositionState(currentNode.value)
  const sd = currentNode.value.sceneDecomposition
  const prevId = sceneDecompEditingId.value
  if (prevId && prevId !== sceneRow.id && sd && normalizeSceneDecompSceneById(sd, prevId)) {
    syncSceneDecompToOutput(currentNode.value)
    persistState()
  }
  sceneDecompEditingId.value = sceneRow.id
}

const finishSceneDecompInlineEdit = () => {
  if (isCompletedNodeReadonly.value) return
  if (!currentNode.value || currentNode.value.name !== '场景分解') return
  const sd = currentNode.value.sceneDecomposition
  const id = sceneDecompEditingId.value
  if (!sd || !id) return
  if (!normalizeSceneDecompSceneById(sd, id)) {
    sceneDecompEditingId.value = null
    return
  }
  syncSceneDecompToOutput(currentNode.value)
  persistState()
  sceneDecompEditingId.value = null
  ElMessage.success('已保存')
}

const createEmptySceneDecompScene = () => {
  if (isCompletedNodeReadonly.value) return
  ensureSceneDecompositionState(currentNode.value)
  const sd = currentNode.value.sceneDecomposition
  sd.filterModule = 'all'
  sd.scenes.push({
    id: `sd-s-${Date.now()}`,
    title: `场景${sd.scenes.length + 1}`,
    text: '',
    updatedAt: new Date().toISOString(),
  })
  syncSceneDecompToOutput(currentNode.value)
  persistState()
  enterSceneDecompInlineEdit(sd.scenes[sd.scenes.length - 1])
}

const runFrameDecompositionAi = async () => {
  if (!currentNode.value || currentNode.value.name !== '画面分解') return
  if (isCompletedNodeReadonly.value) return
  if (!assertStoryboardLlmReady()) return
  if (!assertCurrentNodePromptConfigured()) return
  ensureFrameDecompositionState(currentNode.value)
  const fd = currentNode.value.frameDecomposition
  const userPart = fd.aiModifyText?.trim() || ''
  const target = frameDecompAiTarget.value

  const handleAiError = (e) => {
    const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(String(e?.message || ''))
    if (isTimeout) {
      ElMessage.error('请求超时（大模型响应较慢）。若网络正常可稍后重试。')
      return
    }
    const d = e?.response?.data?.detail
    const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg || x).join('; ') : '生成失败'
    ElMessage.error(msg)
  }

  if (target?.type === 'frame') {
    const scene = fd.scenes.find((x) => x.id === target.sceneId)
    const frameIndex = target.frameIndex
    if (!scene || scene.frames?.[frameIndex] == null) {
      ElMessage.warning('找不到该画面')
      return
    }
    const fr = scene.frames[frameIndex]
    const sceneDesc = getFrameDecompSceneDescription(scene)
    const hasCtx =
      String(sceneDesc || '').trim() ||
      String(fr.description || '').trim() ||
      userPart ||
      frameIndex > 0 ||
      frameIndex < (scene.frames?.length ?? 0) - 1
    if (!hasCtx) {
      ElMessage.warning('请先填写场景/画面信息或补充说明后再试')
      return
    }
    const bodyCore = buildSingleFrameDecompPrompt(scene, frameIndex, '')
    const defaultText = [defaultPromptText.value, bodyCore].filter(Boolean).join('\n\n')
    submitLoading.value = true
    try {
      const { data } = await http.post(
        resolveAiPostUrl(null, 'single-frame-description'),
        buildAiRunBody(defaultText, userPart, currentNode.value.modelId ?? null),
        { timeout: 300000 },
      )
      const out = modelOutputRaw(data)
      const desc =
        data.parse_ok && String(data.description || '').trim()
          ? String(data.description).trim()
          : parseSingleFrameDescriptionResponse(out)
      if (!desc) {
        ElMessage.warning('未能解析模型输出（需要 JSON：{"description":"..."} 或纯文本描述），请重试')
        return
      }
      fr.description = desc
      scene.updatedAt = new Date().toISOString()
      currentNode.value.outputText = out
      fd.aiModifyText = ''
      clearFrameDecompAiTarget()
      closeFdSlashMenu()
      syncFrameDecompToOutput(currentNode.value)
      await persistPipelineAfterGenerate()
      ElMessage.success('已更新该画面')
    } catch (e) {
      handleAiError(e)
    } finally {
      submitLoading.value = false
    }
    return
  }

  if (target?.type === 'scene') {
    const scene = fd.scenes.find((x) => x.id === target.sceneId)
    if (!scene) {
      ElMessage.warning('找不到该场景')
      return
    }
    const sceneDesc = getFrameDecompSceneDescription(scene)
    const hasFrames = (scene.frames || []).some((f) => String(f.description || '').trim())
    if (!String(sceneDesc || '').trim() && !hasFrames && !userPart) {
      ElMessage.warning('请先填写该场景下的画面或补充说明后再试')
      return
    }
    const bodyCore = buildSingleSceneFrameDecompPrompt(scene, '')
    const defaultText = [defaultPromptText.value, bodyCore].filter(Boolean).join('\n\n')
    submitLoading.value = true
    try {
      const { data } = await http.post(
        resolveAiPostUrl(null, 'single-scene-decomposition'),
        buildAiRunBody(defaultText, userPart, currentNode.value.modelId ?? null),
        { timeout: 300000 },
      )
      const out = modelOutputRaw(data)
      let merged = false
      if (data.parse_ok && data.scene) {
        const ts = Date.now()
        scene.title = String(data.scene.title || '').trim() || scene.title
        scene.frames = (data.scene.frames || []).map((f, fi) => ({
          id: `fd-f-${ts}-${fi}`,
          description: String(f.description || '').trim(),
        }))
        scene.updatedAt = new Date().toISOString()
        merged = true
      }
      if (!merged) {
        const parsed = parseFrameDecompositionJson(out)
        if (parsed?.scenes?.length === 1) {
          const one = parsed.scenes[0]
          scene.title = one.title || scene.title
          scene.frames = (one.frames || []).map((f, fi) => ({
            id: f.id || `fd-f-${Date.now()}-${fi}`,
            description: String(f.description || '').trim(),
          }))
          scene.sceneText = one.sceneText || scene.sceneText
          scene.updatedAt = new Date().toISOString()
          merged = true
        }
      }
      if (!merged) {
        ElMessage.warning('模型未返回单场景 JSON（scenes 长度须为 1），请调整说明后重试')
        return
      }
      currentNode.value.outputText = out
      fd.aiModifyText = ''
      clearFrameDecompAiTarget()
      closeFdSlashMenu()
      frameDecompEditingId.value = null
      syncFrameDecompToOutput(currentNode.value)
      await persistPipelineAfterGenerate()
      ElMessage.success('已更新该场景')
    } catch (e) {
      handleAiError(e)
    } finally {
      submitLoading.value = false
    }
    return
  }

  const upPayload = getUpstreamPayloadTextForFrameDecomposition()
  const upstreamCtx = upPayload?.text?.trim()
    ? `\n【上一节点「${upPayload.name}」已定稿场景稿（仅 title/text，供拆画面）】\n${upPayload.text}`
    : ''
  const defaultText = [defaultPromptText.value, upstreamCtx].filter(Boolean).join('\n\n')
  const hasUpstream = !!upstreamCtx
  if (!hasUpstream && !userPart) {
    ElMessage.warning(
      '请先在「场景评审」完成并保存「修改后」场景稿，或填写上方补充说明后再生成画面分解（不再使用本节点已生成的画面 JSON 作为输入）。',
    )
    return
  }
  submitLoading.value = true
  try {
    const { data } = await http.post(
      resolveAiPostUrl('画面分解'),
      buildAiRunBody(defaultText, userPart, currentNode.value.modelId ?? null),
      { timeout: 300000 },
    )
    const out = modelOutputRaw(data)
    let applied = false
    if (data.parse_ok && Array.isArray(data.scenes) && data.scenes.length) {
      fd.scenes = data.scenes.map((s, i) => ({
        id: `fd-s-${i}-${Date.now()}`,
        title: String(s.title || '').trim() || `场景${i + 1}`,
        sceneText: '',
        frames: (s.frames || []).map((f, fi) => ({
          id: `fd-f-${i}-${fi}-${Date.now()}`,
          description: String(f.description || '').trim(),
        })),
        updatedAt: new Date().toISOString(),
      }))
      applied = true
    }
    const parsed = applied ? { scenes: fd.scenes } : parseFrameDecompositionJson(out)
    if (parsed?.scenes?.length) {
      if (!applied) {
        fd.scenes = parsed.scenes.map((s, i) => ({
          ...s,
          updatedAt: new Date().toISOString(),
          id: s.id || `fd-s-${i}-${Date.now()}`,
        }))
      }
      currentNode.value.outputText = out
      fd.aiModifyText = ''
      clearFrameDecompAiTarget()
      closeFdSlashMenu()
      frameDecompEditingId.value = null
      await persistPipelineAfterGenerate()
      ElMessage.success('已更新场景卡片')
    } else {
      ElMessage.warning('模型未返回可解析的 JSON（需包含 scenes 数组），请调整说明后重试')
    }
  } catch (e) {
    handleAiError(e)
  } finally {
    submitLoading.value = false
  }
}

/** 画面分解：当前在内联编辑中的场景 id（无弹窗） */
const frameDecompEditingId = ref(null)

/** 规范化内联编辑中的一条场景并写回 fd.scenes（就地修改） */
const normalizeFrameDecompSceneById = (fd, id) => {
  if (!fd?.scenes || !id) return false
  const idx = fd.scenes.findIndex((s) => s.id === id)
  if (idx < 0) return false
  const s = fd.scenes[idx]
  s.title = String(s.title || '').trim() || `场景${idx + 1}`
  s.frames = (s.frames || []).map((f, fi) => ({
    id: f.id || `fd-f-${fi}-${Date.now()}`,
    description: String(f.description || '').trim(),
  }))
  s.updatedAt = new Date().toISOString()
  return true
}

const enterFrameDecompInlineEdit = (sceneRow) => {
  if (isCompletedNodeReadonly.value) return
  ensureFrameDecompositionState(currentNode.value)
  const fd = currentNode.value.frameDecomposition
  const prevId = frameDecompEditingId.value
  if (prevId && prevId !== sceneRow.id && fd && normalizeFrameDecompSceneById(fd, prevId)) {
    syncFrameDecompToOutput(currentNode.value)
    persistState()
  }
  frameDecompEditingId.value = sceneRow.id
}

const addFrameDecompRow = (s) => {
  if (isCompletedNodeReadonly.value) return
  if (!s.frames) s.frames = []
  s.frames.push({ id: `fd-f-${Date.now()}`, description: '' })
}

const removeFrameDecompRow = (s, fi) => {
  if (isCompletedNodeReadonly.value) return
  if (!s.frames) return
  s.frames.splice(fi, 1)
}

const finishFrameDecompInlineEdit = () => {
  if (isCompletedNodeReadonly.value) return
  if (!currentNode.value || currentNode.value.name !== '画面分解') return
  const fd = currentNode.value.frameDecomposition
  const id = frameDecompEditingId.value
  if (!fd || !id) return
  if (!normalizeFrameDecompSceneById(fd, id)) {
    frameDecompEditingId.value = null
    return
  }
  syncFrameDecompToOutput(currentNode.value)
  persistState()
  frameDecompEditingId.value = null
  ElMessage.success('已保存')
}

const createEmptyFrameDecompScene = () => {
  if (isCompletedNodeReadonly.value) return
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
  enterFrameDecompInlineEdit(fd.scenes[fd.scenes.length - 1])
}

const normSceneReviewField = (v) => {
  if (v == null) return ''
  if (typeof v === 'string') return v
  if (typeof v === 'object') {
    try {
      return JSON.stringify(v, null, 2)
    } catch {
      return String(v)
    }
  }
  return String(v)
}

const unwrapSceneReviewRoot = (o) => {
  if (o == null || typeof o !== 'object') return o
  if (Array.isArray(o) && o.length && typeof o[0] === 'object' && !Array.isArray(o[0])) return o[0]
  const nests = ['data', 'result', 'payload', 'review', 'output', 'body']
  for (const k of nests) {
    const inner = o[k]
    if (inner && typeof inner === 'object' && !Array.isArray(inner)) {
      if (
        '评审结论' in inner ||
        '原内容' in inner ||
        '问题点' in inner ||
        '问题清单及修改建议' in inner ||
        '修改后' in inner ||
        'conclusion' in inner ||
        'original' in inner ||
        'revised' in inner ||
        'issues' in inner ||
        'issue_items' in inner
      ) {
        return inner
      }
    }
  }
  return o
}

const applySceneReviewStructuredToOutput = (node, editScenes) => {
  if (!node || node.name !== '场景评审') return false
  const raw = String(node.outputText || '').trim()
  if (!raw) return false
  const blob = extractJsonObjectString(raw)
  if (!blob) return false
  try {
    const root = JSON.parse(blob)
    const inner = unwrapSceneReviewRoot(root)
    if (!inner || typeof inner !== 'object' || Array.isArray(inner)) return false
    const slim = (editScenes || []).map((s, i) => ({
      title: String(s.title || '').trim() || `场景${i + 1}`,
      text: String(s.text ?? ''),
    }))
    inner.修改后 = { scenes: slim }
    node.outputText = JSON.stringify(root, null, 2)
    return true
  } catch {
    return false
  }
}

const sceneReviewOriginalToStr = (v) => {
  if (v == null) return ''
  if (typeof v === 'object') {
    try {
      return JSON.stringify(v)
    } catch {
      return String(v)
    }
  }
  return String(v).trim()
}

const buildRevisedStorageStringFromScenes = (scenes) => {
  if (!Array.isArray(scenes) || !scenes.length) return ''
  const slim = scenes.map((sc, i) => ({
    title: String(sc.title || '').trim() || `场景${i + 1}`,
    text: String(sc.text ?? ''),
  }))
  return JSON.stringify({ scenes: slim })
}

const formatSceneReviewScenesAsPlain = (scenes) => {
  if (!Array.isArray(scenes) || !scenes.length) return ''
  const jsonLike = JSON.stringify({
    scenes: scenes.map((sc, i) => ({
      title: String(sc.title || '').trim() || `场景${i + 1}`,
      text: String(sc.text ?? ''),
    })),
  })
  return formatReviewPanePlainText(jsonLike) || jsonLike
}

/**
 * 嵌套问题清单：[
 *   { "场景1": [ { "画面1问题": "…", "修改建议": "…" }, … ] },
 *   { "场景2": [ … ] },
 * ]
 */
const parseNestedIssueChecklist = (raw) => {
  if (!Array.isArray(raw) || !raw.length) return []
  const out = []
  for (const block of raw) {
    if (!block || typeof block !== 'object') continue
    for (const sceneKey of Object.keys(block)) {
      const sk = String(sceneKey).trim()
      const arr = block[sceneKey]
      if (!sk || !Array.isArray(arr)) continue
      for (const shot of arr) {
        if (!shot || typeof shot !== 'object') continue
        const suggestion = String(shot.修改建议 ?? shot.suggestion ?? '').trim()
        const parts = []
        for (const k of Object.keys(shot)) {
          if (k === '修改建议' || k === 'suggestion') continue
          const vv = String(shot[k] ?? '').trim()
          const kk = String(k).trim()
          if (vv) parts.push(kk ? `${kk}：${vv}` : vv)
        }
        const problem = parts.join('\n')
        if (problem || suggestion) out.push({ scene: sk, problem, suggestion })
      }
    }
  }
  return out
}

const nestedRowLooksLikeSceneIssueBlock = (row) => {
  if (!row || typeof row !== 'object') return false
  const vals = Object.values(row)
  if (!vals.length) return false
  return vals.every((v) => Array.isArray(v))
}

/** 与后端 _coerce_issue_checklist_raw 一致：数组 | 对象按场景拆块 | JSON 字符串再解析 */
const coerceIssueChecklistRaw = (raw) => {
  if (raw == null) return []
  if (typeof raw === 'string') {
    const s = raw.trim()
    if (!s) return []
    try {
      return coerceIssueChecklistRaw(JSON.parse(s))
    } catch {
      return []
    }
  }
  if (Array.isArray(raw)) return raw
  if (typeof raw === 'object') {
    const blocks = []
    for (const k of Object.keys(raw)) {
      const v = raw[k]
      if (Array.isArray(v)) blocks.push({ [k]: v })
    }
    return blocks
  }
  return []
}

/** 解析「问题清单及修改建议」数组（嵌套场景→多画面条，可与扁平项混排） */
const parseSceneReviewIssueChecklist = (o) => {
  if (!o || typeof o !== 'object') return []
  let raw = o.问题清单及修改建议 ?? o.issue_items ?? o.问题清单 ?? o.issues_detail
  raw = coerceIssueChecklistRaw(raw)
  if (!raw.length) return []
  const out = [...parseNestedIssueChecklist(raw)]
  raw.forEach((row, i) => {
    if (!row || typeof row !== 'object') return
    if (nestedRowLooksLikeSceneIssueBlock(row)) return
    let scene = String(row.场景 ?? row.scene ?? row.场景标签 ?? row.scene_label ?? '').trim()
    if (!scene) scene = `场景${i + 1}`
    const problem = String(
      row.问题 ?? row.具体问题 ?? row.具体问题描述 ?? row.problem ?? row.描述 ?? '',
    ).trim()
    const suggestion = String(row.修改建议 ?? row.建议 ?? row.suggestion ?? '').trim()
    if (!problem && !suggestion) return
    out.push({ scene, problem, suggestion })
  })
  return out
}

/** 写入单场景改稿 prompt 时的问题区文本 */
const formatSceneReviewIssuesBlockForPrompt = (data) => {
  if (data?.issueItems?.length) {
    return data.issueItems
      .map((it) => {
        const head = it.problem
          ? `- ${it.scene}：${it.problem}`
          : `- ${it.scene}：（见下方修改建议）`
        const tail = it.suggestion ? `- 修改建议：${it.suggestion}` : ''
        return [head, tail].filter(Boolean).join('\n')
      })
      .join('\n')
  }
  const lines = (data?.issues || []).map((x) => `- ${x}`)
  return lines.length ? lines.join('\n') : '（无）'
}

/**
 * 解析场景评审 JSON。「修改后」必须为对象且含非空 scenes（与场景分解同构）；不支持字符串或其它旧格式。
 */
const tryParseSceneReviewJson = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s) return { ok: false, reason: '当前节点尚无模型输出，请先点击「生成」。' }
  const blob = extractJsonObjectString(s)
  if (!blob) {
    return {
      ok: false,
      reason:
        '无法从输出中提取完整 JSON 对象。常见原因：模型在 JSON 前后附加了说明文字且无法识别边界、或未输出成对的 { }。请让模型仅输出一段合法 JSON。',
    }
  }
  try {
    let o = JSON.parse(blob)
    o = unwrapSceneReviewRoot(o)
    if (!o || typeof o !== 'object') return { ok: false, reason: '解析后的根节点不是 JSON 对象。' }
    const conclusion = normSceneReviewField(
      o.评审结论 ?? o.conclusion ?? o.summary ?? o['评审结果'] ?? o.总结 ?? '',
    )
    const issueItems = parseSceneReviewIssueChecklist(o)
    let issues = o.问题点 ?? o.issues ?? o.problems ?? o.问题 ?? o.suggestions
    if (issues == null) issues = []
    if (!Array.isArray(issues)) issues = issues ? [String(issues)] : []
    issues = issues.map((x) => String(x))
    if (issueItems.length) {
      issues = []
      issueItems.forEach((it) => {
        if (it.problem) issues.push(`${it.scene}：${it.problem}`)
        else if (it.suggestion) issues.push(`${it.scene}：（见下方修改建议）`)
        if (it.suggestion) issues.push(`修改建议：${it.suggestion}`)
      })
    }
    const originalRaw =
      o.原内容 ??
      o.original ??
      o.before ??
      o.待评审内容 ??
      o.上游内容 ??
      o.原文 ??
      o.场景原文
    const originalStr = sceneReviewOriginalToStr(originalRaw).trim()
    const rawRev = o.修改后 ?? o.revised ?? o.after
    if (rawRev == null || typeof rawRev !== 'object' || Array.isArray(rawRev)) {
      return {
        ok: false,
        reason: '「修改后」必须是 JSON 对象，且包含非空的 scenes 数组（每项 title + text）；不得使用字符串形式的「修改后」。',
      }
    }
    const list = rawRev.scenes ?? rawRev.场景列表
    if (!Array.isArray(list) || !list.length) {
      return {
        ok: false,
        reason: '「修改后.scenes」须为非空数组；请按提示词模板输出与场景分解同构的结构。',
      }
    }
    const revisedScenes = list.map((sc, si) => normalizeSdScene(sc, si))
    const revisedStorage = buildRevisedStorageStringFromScenes(revisedScenes)
    return {
      ok: true,
      data: {
        conclusion: conclusion.trim(),
        issues,
        issueItems,
        original: originalStr,
        revised: revisedStorage,
        revisedScenes,
      },
    }
  } catch (e) {
    return {
      ok: false,
      reason: `JSON 语法错误，无法解析：${e?.message || String(e)}。`,
    }
  }
}

/** 从【标题】块提取正文列表（历史上「修改后」曾误存为可读文本时仍可读） */
const parseSceneBodiesFromBracketFormat = (raw) => {
  const blocks = parseSceneBracketBlocks(raw)
  return blocks ? blocks.map((b) => b.text) : null
}

/** 从一段字符串尽量解析出 scenes[].text 列表（JSON 或【标题】正文） */
const extractSceneTextsFromPossibleJsonOrPlain = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const parsedSd = parseSceneDecompositionJson(s)
  if (parsedSd?.scenes?.length) {
    const texts = parsedSd.scenes.map((sc) => String(sc.text || '').trim())
    if (texts.some((t) => t)) return texts
  }
  const blob = extractJsonObjectString(s)
  if (blob) {
    try {
      const j = JSON.parse(blob)
      const list = j.scenes ?? j.场景列表
      if (Array.isArray(list) && list.length) {
        const texts = list.map((sc) =>
          String(sc?.text ?? sc?.正文 ?? sc?.content ?? sc?.body ?? '').trim(),
        )
        if (texts.some((t) => t)) return texts
      }
    } catch {
      /* ignore */
    }
  }
  return parseSceneBodiesFromBracketFormat(s)
}

/** 从上一节点输出解析出的「每场景一段正文」（与画面分解 scenes 按下标对齐；用于场景描述只读回显） */
const frameDecompUpstreamSceneTexts = computed(() => {
  if (!isFrameDecompositionNode.value) return []
  const up = getImmediateUpstreamOutput()
  const raw = up?.text?.trim() ?? ''
  if (!raw) return []

  const pr = tryParseSceneReviewJson(raw)
  if (pr.ok) {
    let texts = extractSceneTextsFromPossibleJsonOrPlain(pr.data.revised)
    if (!texts?.length || !texts.some((t) => t)) {
      texts = extractSceneTextsFromPossibleJsonOrPlain(pr.data.original)
    }
    if (texts?.length && texts.some((t) => t)) return texts
  }

  const parsedSd = parseSceneDecompositionJson(raw)
  if (parsedSd?.scenes?.length) {
    return parsedSd.scenes.map((sc) => String(sc.text || '').trim())
  }

  return []
})

const getFrameDecompSceneDescription = (s) => {
  const fd = currentNode.value?.frameDecomposition?.scenes ?? []
  const idx = fd.findIndex((x) => x.id === s.id)
  const fromUp = idx >= 0 ? frameDecompUpstreamSceneTexts.value[idx] : ''
  const fromModel = String(s?.sceneText || '').trim()
  return (fromUp || fromModel).trim()
}

const NEIGHBOR_SUMMARY_MAX = 100

const clipNeighborSummary = (text) => {
  const t = String(text || '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!t) return '（空）'
  if (t.length <= NEIGHBOR_SUMMARY_MAX) return t
  return `${t.slice(0, NEIGHBOR_SUMMARY_MAX)}…`
}

const buildSingleFrameDecompPrompt = (scene, frameIndex, userHint) => {
  const sceneDesc = getFrameDecompSceneDescription(scene)
  const frames = scene.frames || []
  const fr = frames[frameIndex]
  const parts = []
  parts.push('【单画面任务】只改写下面「目标画面」，模型输出必须是：{"description":"（新描述）"}')
  parts.push(`【场景】id=${scene.id}\n标题：${scene.title || '未命名'}`)
  parts.push(`【场景正文】\n${sceneDesc || '（无，请结合标题推断）'}`)
  const neigh = []
  if (frameIndex > 0) {
    const p = frames[frameIndex - 1]
    neigh.push(`前一画面（画面${frameIndex}）摘要：${clipNeighborSummary(p.description)}`)
  }
  if (frameIndex < frames.length - 1) {
    const n = frames[frameIndex + 1]
    neigh.push(`后一画面（画面${frameIndex + 2}）摘要：${clipNeighborSummary(n.description)}`)
  }
  if (neigh.length) parts.push(`【衔接参考】\n${neigh.join('\n')}`)
  parts.push(`【目标画面】画面${frameIndex + 1}；frameId=${fr.id}`)
  parts.push(`【当前描述】\n${String(fr.description || '').trim() || '（空，请根据场景生成）'}`)
  if (userHint) parts.push(`【用户补充要求】\n${userHint}`)
  return parts.join('\n\n')
}

const buildSingleSceneFrameDecompPrompt = (scene, userHint) => {
  const sceneDesc = getFrameDecompSceneDescription(scene)
  const slim = {
    title: scene.title || '未命名场景',
    frames: (scene.frames || []).map((f) => ({ description: String(f.description || '').trim() })),
  }
  const parts = []
  parts.push(
    '【单场景任务】只输出 {"scenes":[{"title":"...","frames":[{"description":"..."}]}]} ，且 scenes 必须恰好 1 项。',
  )
  parts.push(`【场景】id=${scene.id}`)
  parts.push(`【场景正文】\n${sceneDesc || '（无）'}`)
  parts.push(`【当前分镜 JSON（仅本场景）】\n${JSON.stringify({ scenes: [slim] }, null, 2)}`)
  if (userHint) parts.push(`【用户补充要求】\n${userHint}`)
  return parts.join('\n\n')
}

const buildSingleSceneCardDecompPrompt = (sceneRow, sd) => {
  const parts = []
  parts.push(
    '【单场景卡片任务】只输出 {\"scenes\":[{\"title\":\"...\",\"text\":\"...\"}]} ，且 scenes 必须恰好 1 项。',
  )
  parts.push(`【场景】id=${sceneRow.id}`)
  parts.push(`【当前标题】${sceneRow.title || '未命名'}`)
  parts.push(`【当前正文】\n${String(sceneRow.text || '').trim() || '（空）'}`)
  const others = (sd.scenes || [])
    .filter((x) => x.id !== sceneRow.id)
    .map((x, i) => `${i + 1}. ${x.title || '未命名'}`)
  if (others.length) {
    parts.push(`【同表中其它场景标题（勿改写，仅作衔接参考）】\n${others.join('\n')}`)
  }
  parts.push(
    `【完整表 JSON（便于对照位置）】\n${JSON.stringify(
      { scenes: (sd.scenes || []).map((s) => ({ id: s.id, title: s.title, text: s.text })) },
      null,
      2,
    )}`,
  )
  return parts.join('\n\n')
}

const parseSingleFrameDescriptionResponse = (raw) => {
  const s = String(raw || '').trim()
  const blob = extractJsonObjectString(s)
  if (blob) {
    try {
      const o = JSON.parse(blob)
      if (o && typeof o === 'object') {
        const d = o.description ?? o.描述 ?? o.text ?? o.content
        if (typeof d === 'string' && d.trim()) return d.trim()
      }
    } catch {
      /* fall through */
    }
  }
  let plain = s
  const fence = plain.match(/^```(?:\w+)?\s*([\s\S]*?)```/m)
  if (fence) plain = fence[1].trim()
  if (plain && !/^\s*\{/.test(plain)) return plain.trim()
  return null
}

/** 画面分解：AI 输入框 / 菜单与提交目标（null=整表） */
const fdAiInputRef = ref(null)
const fdAiTextareaWrapRef = ref(null)
const frameDecompAiTarget = ref(null)
const fdSlashMenuVisible = ref(false)
const fdSlashStart = ref(-1)
const fdSlashFilter = ref('')
const fdSlashHighlight = ref(0)
const fdSlashMenuStyle = ref({
  top: '0px',
  left: '0px',
  minWidth: '200px',
  maxWidth: '360px',
})

let fdSlashRepositionListeners = null
const detachFdSlashRepositionListeners = () => {
  if (!fdSlashRepositionListeners) return
  const { ta, fn } = fdSlashRepositionListeners
  ta?.removeEventListener('scroll', fn)
  window.removeEventListener('resize', fn)
  fdSlashRepositionListeners = null
}

/** Element Plus el-input 内部 textarea：优先用实例暴露的 textarea，避免 $el 下找不到节点 */
const getFdAiTextareaEl = () => {
  const inst = fdAiInputRef.value
  if (!inst) return null
  const exposed = inst.textarea
  if (exposed != null) {
    const el = unref(exposed)
    if (el instanceof HTMLTextAreaElement) return el
  }
  return inst.$el?.querySelector?.('textarea') ?? null
}

const closeFdSlashMenu = () => {
  fdSlashMenuVisible.value = false
  fdSlashStart.value = -1
  fdSlashFilter.value = ''
}

const clearFrameDecompAiTarget = () => {
  if (currentNode.value?.completed) return
  frameDecompAiTarget.value = null
}

const fdSlashFilteredOptions = computed(() => {
  if (!isFrameDecompositionNode.value) return []
  const fd = currentNode.value?.frameDecomposition
  const q = (fdSlashFilter.value || '').trim().toLowerCase()
  const opts = []
  opts.push({ key: 'all', label: '整表（所有场景与画面）', pick: { type: 'all' } })
  if (!fd?.scenes?.length) {
    return !q ? opts : opts.filter((o) => o.label.toLowerCase().includes(q))
  }
  fd.scenes.forEach((s, si) => {
    const st = String(s.title || '').trim() || `场景${si + 1}`
    opts.push({ key: `s-${s.id}`, label: `场景：${st}`, pick: { type: 'scene', sceneId: s.id } })
    ;(s.frames || []).forEach((fr, fi) => {
      opts.push({
        key: `f-${s.id}-${fi}`,
        label: `场景「${st}」· 画面${fi + 1}`,
        pick: { type: 'frame', sceneId: s.id, frameIndex: fi },
      })
    })
  })
  if (!q) return opts
  return opts.filter((o) => o.label.toLowerCase().includes(q))
})

/** 左侧蓝色范围条文案（整表 / 场景 / 画面） */
const frameDecompScopeChipText = computed(() => {
  const t = frameDecompAiTarget.value
  const fd = currentNode.value?.frameDecomposition
  if (!t || t.type === 'all') return '整表'
  const sc = fd?.scenes?.find((s) => s.id === t.sceneId)
  const title = sc?.title || '未命名场景'
  if (t.type === 'scene') return `场景「${title}」`
  return `「${title}」· 画面${t.frameIndex + 1}`
})

const frameDecompScopeTitle = computed(() => {
  const t = frameDecompAiTarget.value
  if (!t || t.type === 'all') return '当前范围：所有场景与画面（整表）'
  const fd = currentNode.value?.frameDecomposition
  const sc = fd?.scenes?.find((s) => s.id === t.sceneId)
  const title = sc?.title || '未命名场景'
  if (t.type === 'scene') return `当前范围：场景「${title}」`
  return `当前范围：场景「${title}」· 画面${t.frameIndex + 1}`
})

/** 镜像测量 textarea 内光标位置（相对 textarea 可视区域，含 padding/border） */
const getTextareaCaretBox = (ta, caretPos) => {
  const cs = getComputedStyle(ta)
  const mirror = document.createElement('div')
  mirror.setAttribute('aria-hidden', 'true')
  mirror.style.cssText = [
    'position:absolute',
    'left:-9999px',
    'top:0',
    'visibility:hidden',
    'white-space:pre-wrap',
    'word-wrap:break-word',
    'overflow:hidden',
    'box-sizing:border-box',
    `width:${ta.clientWidth}px`,
    `font:${cs.font}`,
    `padding:${cs.padding}`,
    `border:${cs.border}`,
    `line-height:${cs.lineHeight}`,
    `letter-spacing:${cs.letterSpacing}`,
    `text-indent:${cs.textIndent}`,
  ].join(';')
  mirror.textContent = ta.value.slice(0, caretPos)
  const marker = document.createElement('span')
  marker.textContent = '\u200b'
  mirror.appendChild(marker)
  document.body.appendChild(mirror)
  const ct = marker.offsetTop
  const cl = marker.offsetLeft
  document.body.removeChild(mirror)
  const lhRaw = parseFloat(cs.lineHeight)
  const fs = parseFloat(cs.fontSize) || 14
  const lineHeight = Number.isFinite(lhRaw) && lhRaw > 0 ? lhRaw : Math.round(fs * 1.25)
  const bTop = parseFloat(cs.borderTopWidth) || 0
  const bLeft = parseFloat(cs.borderLeftWidth) || 0
  const pTop = parseFloat(cs.paddingTop) || 0
  const pLeft = parseFloat(cs.paddingLeft) || 0
  return {
    yCaret: bTop + pTop + ct - ta.scrollTop,
    xCaret: bLeft + pLeft + cl - ta.scrollLeft,
    lineHeight,
  }
}

/** 场景分解：/ 菜单与单卡提交目标（null=整表） */
const sdAiInputRef = ref(null)
const sdAiTextareaWrapRef = ref(null)
const sceneDecompAiTarget = ref(null)
const sdSlashMenuVisible = ref(false)
const sdSlashStart = ref(-1)
const sdSlashFilter = ref('')
const sdSlashHighlight = ref(0)
const sdSlashMenuStyle = ref({
  top: '0px',
  left: '0px',
  minWidth: '200px',
  maxWidth: '360px',
})

let sdSlashRepositionListeners = null
const detachSdSlashRepositionListeners = () => {
  if (!sdSlashRepositionListeners) return
  const { ta, fn } = sdSlashRepositionListeners
  ta?.removeEventListener('scroll', fn)
  window.removeEventListener('resize', fn)
  sdSlashRepositionListeners = null
}

const getSdAiTextareaEl = () => {
  const inst = sdAiInputRef.value
  if (!inst) return null
  const exposed = inst.textarea
  if (exposed != null) {
    const el = unref(exposed)
    if (el instanceof HTMLTextAreaElement) return el
  }
  return inst.$el?.querySelector?.('textarea') ?? null
}

const closeSdSlashMenu = () => {
  sdSlashMenuVisible.value = false
  sdSlashStart.value = -1
  sdSlashFilter.value = ''
}

const clearSceneDecompAiTarget = () => {
  if (currentNode.value?.completed) return
  sceneDecompAiTarget.value = null
}

const sdSlashFilteredOptions = computed(() => {
  if (!isSceneDecompositionNode.value) return []
  const sd = currentNode.value?.sceneDecomposition
  const q = (sdSlashFilter.value || '').trim().toLowerCase()
  const opts = []
  opts.push({ key: 'all', label: '整表（所有场景卡片）', pick: { type: 'all' } })
  if (!sd?.scenes?.length) {
    return !q ? opts : opts.filter((o) => o.label.toLowerCase().includes(q))
  }
  sd.scenes.forEach((s, si) => {
    const st = String(s.title || '').trim() || `场景${si + 1}`
    opts.push({ key: `s-${s.id}`, label: `场景：${st}`, pick: { type: 'scene', sceneId: s.id } })
  })
  if (!q) return opts
  return opts.filter((o) => o.label.toLowerCase().includes(q))
})

const sceneDecompScopeChipText = computed(() => {
  const t = sceneDecompAiTarget.value
  const sd = currentNode.value?.sceneDecomposition
  if (!t || t.type === 'all') return '整表'
  const sc = sd?.scenes?.find((s) => s.id === t.sceneId)
  const title = sc?.title || '未命名场景'
  return `场景「${title}」`
})

const sceneDecompScopeTitle = computed(() => {
  const t = sceneDecompAiTarget.value
  if (!t || t.type === 'all') return '当前范围：所有场景卡片（整表）'
  const sd = currentNode.value?.sceneDecomposition
  const sc = sd?.scenes?.find((s) => s.id === t.sceneId)
  const title = sc?.title || '未命名场景'
  return `当前范围：场景「${title}」`
})

const positionSdSlashMenu = () => {
  const wrap = sdAiTextareaWrapRef.value
  const ta = getSdAiTextareaEl()
  if (!wrap || !ta || !sdSlashMenuVisible.value) return
  const pos = ta.selectionStart
  const { yCaret, xCaret, lineHeight } = getTextareaCaretBox(ta, pos)
  const taRect = ta.getBoundingClientRect()
  const wrapRect = wrap.getBoundingClientRect()
  const gap = 2
  let top = taRect.top - wrapRect.top + yCaret + lineHeight + gap
  let left = taRect.left - wrapRect.left + xCaret
  const menuMinW = 200
  const edgePad = 6
  let maxW = wrapRect.width - left - edgePad
  if (maxW < menuMinW) {
    left = Math.max(edgePad, wrapRect.width - menuMinW - edgePad)
    maxW = wrapRect.width - left - edgePad
  }
  sdSlashMenuStyle.value = {
    top: `${Math.max(0, top)}px`,
    left: `${Math.max(0, left)}px`,
    minWidth: `${menuMinW}px`,
    maxWidth: `${Math.max(menuMinW, maxW)}px`,
  }
}

const schedulePositionSdSlashMenu = () => {
  if (!sdSlashMenuVisible.value) return
  nextTick(() => {
    requestAnimationFrame(() => positionSdSlashMenu())
  })
}

const attachSdSlashRepositionListeners = () => {
  detachSdSlashRepositionListeners()
  const fn = () => positionSdSlashMenu()
  const ta = getSdAiTextareaEl()
  if (ta) ta.addEventListener('scroll', fn, { passive: true })
  window.addEventListener('resize', fn, { passive: true })
  sdSlashRepositionListeners = { ta, fn }
}

watch(sdSlashMenuVisible, (v) => {
  if (v) {
    nextTick(() => {
      requestAnimationFrame(() => {
        positionSdSlashMenu()
        attachSdSlashRepositionListeners()
      })
    })
  } else {
    detachSdSlashRepositionListeners()
  }
})

const pickSdSlashOption = (opt) => {
  const sd = currentNode.value?.sceneDecomposition
  if (!sd) {
    closeSdSlashMenu()
    return
  }
  const ta = getSdAiTextareaEl()
  if (ta && sdSlashMenuVisible.value && sdSlashStart.value >= 0) {
    const start = sdSlashStart.value
    const end = ta.selectionStart
    const v0 = sd.aiModifyText || ''
    sd.aiModifyText = v0.slice(0, start) + v0.slice(end)
    nextTick(() => {
      const el = getSdAiTextareaEl()
      if (el) {
        el.focus()
        const pos = start
        el.selectionStart = el.selectionEnd = pos
      }
    })
  }
  if (opt.pick.type === 'all') sceneDecompAiTarget.value = null
  else sceneDecompAiTarget.value = opt.pick
  closeSdSlashMenu()
}

const syncSdSlashFromTextarea = () => {
  if (!isSceneDecompositionNode.value) return
  const ta = getSdAiTextareaEl()
  if (!ta) return
  const v = ta.value || ''
  const pos = ta.selectionStart

  if (sdSlashMenuVisible.value) {
    if (sdSlashStart.value < 0 || v[sdSlashStart.value] !== '/') {
      closeSdSlashMenu()
      return
    }
    const q = v.slice(sdSlashStart.value + 1, pos)
    if (q.includes('\n')) {
      closeSdSlashMenu()
      return
    }
    sdSlashFilter.value = q
    sdSlashHighlight.value = 0
    schedulePositionSdSlashMenu()
    return
  }

  if (pos > 0 && v[pos - 1] === '/') {
    sdSlashMenuVisible.value = true
    sdSlashStart.value = pos - 1
    sdSlashFilter.value = ''
    sdSlashHighlight.value = 0
    schedulePositionSdSlashMenu()
  }
}

const onSdAiKeydown = (e) => {
  if (!isSceneDecompositionNode.value) return
  const opts = sdSlashFilteredOptions.value
  if (e.key === 'Escape' && sdSlashMenuVisible.value) {
    e.preventDefault()
    closeSdSlashMenu()
    return
  }
  if (sdSlashMenuVisible.value && opts.length) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      sdSlashHighlight.value = (sdSlashHighlight.value + 1) % opts.length
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      sdSlashHighlight.value = (sdSlashHighlight.value - 1 + opts.length) % opts.length
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      pickSdSlashOption(opts[sdSlashHighlight.value])
      return
    }
  }
  if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    requestAnimationFrame(() => {
      syncSdSlashFromTextarea()
    })
  }
}

const onSdAiInput = () => {
  nextTick(() => {
    requestAnimationFrame(() => {
      syncSdSlashFromTextarea()
    })
  })
}

watch(isSceneDecompositionNode, (v) => {
  if (!v) {
    closeSdSlashMenu()
    clearSceneDecompAiTarget()
    sceneDecompEditingId.value = null
  }
})

const positionFdSlashMenu = () => {
  const wrap = fdAiTextareaWrapRef.value
  const ta = getFdAiTextareaEl()
  if (!wrap || !ta || !fdSlashMenuVisible.value) return
  const pos = ta.selectionStart
  const { yCaret, xCaret, lineHeight } = getTextareaCaretBox(ta, pos)
  const taRect = ta.getBoundingClientRect()
  const wrapRect = wrap.getBoundingClientRect()
  const gap = 2
  let top = taRect.top - wrapRect.top + yCaret + lineHeight + gap
  let left = taRect.left - wrapRect.left + xCaret
  const menuMinW = 200
  const edgePad = 6
  let maxW = wrapRect.width - left - edgePad
  if (maxW < menuMinW) {
    left = Math.max(edgePad, wrapRect.width - menuMinW - edgePad)
    maxW = wrapRect.width - left - edgePad
  }
  fdSlashMenuStyle.value = {
    top: `${Math.max(0, top)}px`,
    left: `${Math.max(0, left)}px`,
    minWidth: `${menuMinW}px`,
    maxWidth: `${Math.max(menuMinW, maxW)}px`,
  }
}

const schedulePositionFdSlashMenu = () => {
  if (!fdSlashMenuVisible.value) return
  nextTick(() => {
    requestAnimationFrame(() => positionFdSlashMenu())
  })
}

const attachFdSlashRepositionListeners = () => {
  detachFdSlashRepositionListeners()
  const fn = () => positionFdSlashMenu()
  const ta = getFdAiTextareaEl()
  if (ta) ta.addEventListener('scroll', fn, { passive: true })
  window.addEventListener('resize', fn, { passive: true })
  fdSlashRepositionListeners = { ta, fn }
}

watch(fdSlashMenuVisible, (v) => {
  if (v) {
    nextTick(() => {
      requestAnimationFrame(() => {
        positionFdSlashMenu()
        attachFdSlashRepositionListeners()
      })
    })
  } else {
    detachFdSlashRepositionListeners()
  }
})

onBeforeUnmount(() => {
  detachFdSlashRepositionListeners()
  detachSdSlashRepositionListeners()
})

const pickFdSlashOption = (opt) => {
  const fd = currentNode.value?.frameDecomposition
  if (!fd) {
    closeFdSlashMenu()
    return
  }
  const ta = getFdAiTextareaEl()
  if (ta && fdSlashMenuVisible.value && fdSlashStart.value >= 0) {
    const start = fdSlashStart.value
    const end = ta.selectionStart
    const v = fd.aiModifyText || ''
    fd.aiModifyText = v.slice(0, start) + v.slice(end)
    nextTick(() => {
      const el = getFdAiTextareaEl()
      if (el) {
        el.focus()
        const pos = start
        el.selectionStart = el.selectionEnd = pos
      }
    })
  }
  if (opt.pick.type === 'all') frameDecompAiTarget.value = null
  else frameDecompAiTarget.value = opt.pick
  closeFdSlashMenu()
}

const syncFdSlashFromTextarea = () => {
  if (!isFrameDecompositionNode.value) return
  const ta = getFdAiTextareaEl()
  if (!ta) return
  const v = ta.value || ''
  const pos = ta.selectionStart

  if (fdSlashMenuVisible.value) {
    if (fdSlashStart.value < 0 || v[fdSlashStart.value] !== '/') {
      closeFdSlashMenu()
      return
    }
    const q = v.slice(fdSlashStart.value + 1, pos)
    if (q.includes('\n')) {
      closeFdSlashMenu()
      return
    }
    fdSlashFilter.value = q
    fdSlashHighlight.value = 0
    schedulePositionFdSlashMenu()
    return
  }

  if (pos > 0 && v[pos - 1] === '/') {
    fdSlashMenuVisible.value = true
    fdSlashStart.value = pos - 1
    fdSlashFilter.value = ''
    fdSlashHighlight.value = 0
    schedulePositionFdSlashMenu()
  }
}

const onFdAiKeydown = (e) => {
  if (!isFrameDecompositionNode.value) return
  const opts = fdSlashFilteredOptions.value
  if (e.key === 'Escape' && fdSlashMenuVisible.value) {
    e.preventDefault()
    closeFdSlashMenu()
    return
  }
  if (fdSlashMenuVisible.value && opts.length) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      fdSlashHighlight.value = (fdSlashHighlight.value + 1) % opts.length
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      fdSlashHighlight.value = (fdSlashHighlight.value - 1 + opts.length) % opts.length
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      pickFdSlashOption(opts[fdSlashHighlight.value])
      return
    }
  }
  /* keydown 时默认行为尚未写入字符，需在下一帧再读 textarea；el-input 的 @input 也会再同步一次 */
  if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    requestAnimationFrame(() => {
      syncFdSlashFromTextarea()
    })
  }
}

/** el-input 的 input 只传 value，用 nextTick + rAF 保证与 v-model、光标一致后再解析 / */
const onFdAiInput = () => {
  nextTick(() => {
    requestAnimationFrame(() => {
      syncFdSlashFromTextarea()
    })
  })
}

/** 场景评审「原内容 / 修改后」栏：若为场景或分镜 JSON，转为可读纯文本，避免满屏 JSON 符号 */
const formatReviewPanePlainText = (raw) => {
  if (raw == null) return ''
  const s = String(raw).trim()
  if (!s) return ''
  const blob = extractJsonObjectString(s)
  if (!blob) return s
  try {
    const o = JSON.parse(blob)
    if (!o || typeof o !== 'object') return s
    if (typeof o.story === 'string' && o.story.trim()) return o.story.trim()
    const list = o.scenes ?? o.场景列表
    if (!Array.isArray(list) || list.length === 0) return s
    const hasFrames = list.some((sc) => {
      const fr = sc?.frames ?? sc?.画面
      return Array.isArray(fr) && fr.length > 0
    })
    if (hasFrames) {
      return list
        .map((sc, i) => {
          const title = sc?.title ?? sc?.标题 ?? `场景${i + 1}`
          let fr = sc?.frames ?? sc?.画面 ?? []
          if (!Array.isArray(fr)) fr = []
          const lines = fr.map((f, fi) => {
            const d =
              typeof f === 'string'
                ? f.trim()
                : String(f?.description ?? f?.描述 ?? f?.text ?? '').trim()
            // 描述里若含换行，不压成单行则「· 画面N：」下一行无法被解析，保存后内容会截断/错乱
            const dOneLine = d.replace(/\s*\r?\n\s*/g, ' ').trim()
            return `  · 画面${fi + 1}：${dOneLine || '—'}`
          })
          return `【${title}】\n${lines.join('\n') || '  （无画面描述）'}`
        })
        .join('\n\n')
    }
    return list
      .map((sc, i) => {
        const title = sc?.title ?? sc?.标题 ?? `场景${i + 1}`
        let body =
          sc?.text ??
          sc?.正文 ??
          sc?.content ??
          sc?.body ??
          sc?.description ??
          sc?.描述 ??
          ''
        body = String(body).trim()
        if (!body) {
          const parts = []
          const loc = sc?.location ?? sc?.地点
          const tim = sc?.time ?? sc?.时间
          const ch = sc?.characters ?? sc?.人物 ?? sc?.出场人物
          const cf = sc?.conflict ?? sc?.冲突 ?? sc?.冲突点
          const vf = sc?.visualFocus ?? sc?.视觉 ?? sc?.视觉重点
          if (loc) parts.push(`地点：${loc}`)
          if (tim) parts.push(`时间：${tim}`)
          if (ch) parts.push(`人物：${ch}`)
          if (cf) parts.push(`冲突：${cf}`)
          if (vf) parts.push(`视觉：${vf}`)
          body = parts.join('\n')
        }
        return `【${title}】\n${body || '（无正文）'}`
      })
      .join('\n\n')
  } catch {
    return s
  }
}

/** 画面评审「优化分镜」结构 → 与 formatReviewPanePlainText 一致的可读稿（用于对比 / 复制 / 会话基线） */
const formatOptimizedScenesAsPlain = (scenes) => {
  if (!Array.isArray(scenes) || !scenes.length) return ''
  const jsonLike = JSON.stringify({
    scenes: scenes.map((sc) => ({
      title: sc.title,
      frames: (sc.frames || []).map((f) => ({ description: String(f?.description ?? '') })),
    })),
  })
  return formatReviewPanePlainText(jsonLike) || jsonLike
}

/** 按空行切成段落再 diff，便于「一整段改了」整块标色；单段内仍做字符级 diff。 */
const splitReviewParagraphs = (s) => {
  const str = String(s ?? '')
  if (!str.trim()) return []
  const paras = str.split(/\r?\n\s*\r?\n/).filter((chunk) => chunk.length > 0)
  return paras.length ? paras : [str]
}

const mergeAdjacentSameDiffOp = (diffs) => {
  if (!diffs.length) return []
  const out = [[diffs[0][0], diffs[0][1]]]
  for (let i = 1; i < diffs.length; i++) {
    const op = diffs[i][0]
    const txt = diffs[i][1]
    const last = out[out.length - 1]
    if (last[0] === op) last[1] += txt
    else out.push([op, txt])
  }
  return out
}

/** 评审前/后：未改动黑字；有改动的片段左栏浅红（改动前）、右栏浅绿（改动后），不区分删除/新增语义 */
const buildReviewTextDiff = (textA, textB) => {
  const sep = '\uE000'
  const blocksA = splitReviewParagraphs(textA)
  const blocksB = splitReviewParagraphs(textB)
  const joinA = blocksA.join(sep)
  const joinB = blocksB.join(sep)
  const dmp = new DiffMatchPatch()
  let diffs = dmp.diff_main(joinA, joinB)
  dmp.diff_cleanupSemantic(diffs)
  diffs = mergeAdjacentSameDiffOp(diffs)
  const left = []
  const right = []
  const unwrap = (t) => t.split(sep).join('\n\n')
  for (let i = 0; i < diffs.length; i++) {
    const op = diffs[i][0]
    const txt = unwrap(diffs[i][1])
    if (op === 0) {
      left.push({ op: 'eq', text: txt })
      right.push({ op: 'eq', text: txt })
    } else if (op === -1) {
      left.push({ op: 'before', text: txt })
    } else if (op === 1) {
      right.push({ op: 'after', text: txt })
    }
  }
  return { left, right }
}

/** 去掉模型常见的整体 markdown 代码围栏（与其它节点 strip 逻辑一致） */
const stripModelPlainOutput = (raw) => {
  let t = String(raw || '').trim()
  const fence = t.match(/^```(?:\w+)?\s*([\s\S]*?)```/m)
  if (fence) t = fence[1].trim()
  return t
}

const parseStoryJson = (raw) => {
  const text = extractJsonObjectString(raw)
  if (!text) return null
  try {
    const o = JSON.parse(text)
    if (!o || typeof o !== 'object') return null
    const story = o.story ?? o.故事 ?? o.故事梗概 ?? o.正文 ?? o.content
    if (story == null || String(story).trim() === '') return null
    return { story: String(story) }
  } catch {
    return null
  }
}

/** 故事描述：支持 JSON 中的 story 等键，或直接输出纯文本（与后端 parse_story_description 一致） */
const parseStoryDescriptionDisplay = (raw) => {
  const s = String(raw || '').trim()
  if (!s) return null
  const j = parseStoryJson(s)
  if (j) return j
  const plain = stripModelPlainOutput(s)
  const t = String(plain || '').trim()
  if (!t) return null
  return { story: t }
}

const unwrapFrameReviewRoot = (o) => {
  if (o == null || typeof o !== 'object') return o
  if (Array.isArray(o) && o.length && typeof o[0] === 'object' && !Array.isArray(o[0])) return o[0]
  const nests = ['data', 'result', 'payload', 'review', 'output', 'body']
  for (const k of nests) {
    const inner = o[k]
    if (inner && typeof inner === 'object' && !Array.isArray(inner)) {
      if (
        '总评' in inner ||
        '评审结论' in inner ||
        'conclusion' in inner ||
        'summary' in inner ||
        '优化分镜' in inner ||
        '修改后' in inner ||
        'modified' in inner ||
        'final' in inner ||
        '问题清单及修改建议' in inner ||
        '原内容' in inner ||
        '优点' in inner ||
        '改进建议' in inner
      ) {
        return inner
      }
    }
  }
  return o
}

/** 画面评审「修改后」：对象 { scenes }、JSON 字符串、或直接 scenes 数组（与后端 parse 对齐） */
const parseFrameReviewModifiedToScenes = (mod) => {
  if (mod == null) return []
  let m = mod
  if (typeof m === 'string') {
    const s = m.trim()
    if (!s) return []
    try {
      m = JSON.parse(s)
    } catch {
      return []
    }
  }
  const mapOneScene = (item, i, titleFallback) => {
    const title = String(item?.title ?? item?.标题 ?? item?.name ?? item?.sceneTitle ?? item?.场景标题 ?? '').trim()
    let fr = item?.frames ?? item?.画面 ?? item?.shots ?? item?.镜头列表 ?? []
    if (!Array.isArray(fr)) fr = []
    const frames = fr.map((f) => ({
      description: String(
        typeof f === 'string'
          ? f
          : (f?.description ??
              f?.描述 ??
              f?.画面描述 ??
              f?.镜头描述 ??
              f?.text ??
              f?.content ??
              f?.镜头 ??
              ''),
      ).trim(),
    }))
    return { title: title || titleFallback, frames }
  }
  if (Array.isArray(m)) {
    return m.map((item, i) => mapOneScene(item, i, `场景${i + 1}`))
  }
  if (typeof m === 'object' && m) {
    const list = m.scenes ?? m.场景列表
    if (!Array.isArray(list) || !list.length) return []
    return list.map((item, i) => mapOneScene(item, i, `场景${i + 1}`))
  }
  return []
}

/** 从画面评审根对象各键尝试取出优化分镜（与 parse_frame_review 后端逻辑对齐） */
const tryOptimizedScenesFromFrameReviewRoot = (o) => {
  if (!o || typeof o !== 'object') return []
  let scenes = parseFrameReviewModifiedToScenes(
    o.修改后 ?? o.revised ?? o.after ?? o.modified ?? o.final,
  )
  if (scenes.length) return scenes
  scenes = parseFrameReviewModifiedToScenes(
    o.优化分镜 ?? o.optimizedScenes ?? o.framesReview ?? o.optimized_scenes,
  )
  if (scenes.length) return scenes
  return parseFrameReviewModifiedToScenes(o.scenes ?? o.场景列表)
}

const parseFrameReviewJson = (raw) => {
  const text = extractStructuredJsonBlob(raw)
  if (!text) return null
  try {
    let o = JSON.parse(text)
    if (!o || typeof o !== 'object') return null
    o = unwrapFrameReviewRoot(o)
    const summary = String(o.评审结论 ?? o.总评 ?? o.summary ?? o.conclusion ?? '').trim()
    const issueItems = parseSceneReviewIssueChecklist(o)
    const original = sceneReviewOriginalToStr(
      o.原内容 ?? o.original ?? o.before ?? o.待评审分镜 ?? o.上游内容 ?? '',
    ).trim()
    let merits = o.优点 ?? o.merits
    if (merits == null) merits = []
    if (!Array.isArray(merits)) merits = merits ? [String(merits)] : []
    merits = merits.map((x) => String(x))
    let suggestions = o.改进建议 ?? o.suggestions ?? o.改进点
    if (suggestions == null) suggestions = []
    if (!Array.isArray(suggestions)) suggestions = suggestions ? [String(suggestions)] : []
    suggestions = suggestions.map((x) => String(x))
    const scenes = tryOptimizedScenesFromFrameReviewRoot(o)
    if (!summary && !merits.length && !suggestions.length && !scenes.length && !issueItems.length && !original)
      return null
    return { summary, merits, suggestions, scenes, issueItems, original }
  } catch {
    return null
  }
}

const findPipelineNodeByName = (name) => nodes.value.find((n) => n.name === name && n.enabled !== false)

const getSceneListForFullContent = () => {
  const srNode = findPipelineNodeByName('场景评审')
  if (srNode?.outputText?.trim()) {
    const pr = tryParseSceneReviewJson(srNode.outputText)
    if (pr.ok && pr.data.revisedScenes?.length) {
      return pr.data.revisedScenes.map((s) => ({
        title: String(s.title || ''),
        text: String(s.text || ''),
      }))
    }
  }
  const sdNode = findPipelineNodeByName('场景分解')
  if (sdNode?.outputText) {
    const p = parseSceneDecompositionJson(sdNode.outputText)
    if (p?.scenes?.length) {
      return p.scenes.map((s) => ({ title: String(s.title || ''), text: String(s.text || '') }))
    }
  }
  return []
}

/** 避免标题里已有「场景1：」时与【场景1：】重复 */
const stripLeadingSceneIndexForFcg = (title, index1) => {
  const raw = String(title || '').trim()
  if (!raw) return ''
  const re = new RegExp(`^场景\\s*${Number(index1)}\\s*[：:]\\s*`)
  return raw.replace(re, '').trim() || raw
}

/** 完整内容的分镜结构只来自「画面评审」JSON 中的「优化分镜」：每场景 frames 有几条就展示几幅，不用画面分解阶段数据。 */
const getFrameScenesForFullContent = () => {
  const frNode = findPipelineNodeByName('画面评审')
  if (!frNode?.outputText?.trim()) return []
  const d = parseFrameReviewJson(frNode.outputText)
  if (!d?.scenes?.length) return []
  return d.scenes
}

/**
 * 从上游解析出的 scenes/frames 可能与画面分解等 UI 状态共享引用；合并时 push 会改到原数组，
 * 进而污染 outputText。此处深拷贝为纯 { description }，与流水线其它节点隔离。
 */
const cloneFrameScenesForPipeline = (frameScenes) => {
  if (!Array.isArray(frameScenes) || !frameScenes.length) return []
  return frameScenes.map((fs) => ({
    title: fs?.title,
    sceneText: String(fs?.sceneText ?? '').trim(),
    frames: (fs?.frames || []).map((f) => ({
      description: String(
        typeof f === 'string' ? f : (f?.description ?? f?.描述 ?? f?.text ?? ''),
      ).trim(),
    })),
  }))
}

/**
 * 画面 JSON 有时把「同一逻辑场景」拆成多条 scenes（每条只有 1 个 frame），
 * 或与场景分解条数不一致。合并后保证：一个场景卡片内嵌多幅画面，而不是多张小场景卡。
 */
const mergeFrameScenesForFullContent = (frameScenes, sceneMetas) => {
  if (!Array.isArray(frameScenes) || frameScenes.length === 0) return frameScenes
  const metas = Array.isArray(sceneMetas) ? sceneMetas : []
  const normTitle = (t) => String(t || '').trim().replace(/\s+/g, ' ')

  let list = cloneFrameScenesForPipeline(frameScenes)

  const mergedByTitle = []
  for (const row of list) {
    const t = normTitle(row.title)
    const last = mergedByTitle[mergedByTitle.length - 1]
    if (last && normTitle(last.title) === t && t !== '') {
      last.frames.push(...row.frames)
      if (row.sceneText) {
        last.sceneText = last.sceneText ? `${last.sceneText}\n\n${row.sceneText}` : row.sceneText
      }
    } else {
      mergedByTitle.push({ title: row.title, frames: [...row.frames], sceneText: row.sceneText })
    }
  }
  list = mergedByTitle

  const metaCount = metas.length
  if (metaCount === 1 && list.length > 1) {
    const allFrames = list.flatMap((x) => x.frames)
    const stFromRows = list.map((x) => x.sceneText).filter(Boolean).join('\n\n')
    const title0 = String(metas[0]?.title || list[0]?.title || '场景1').trim() || '场景1'
    const st0 = String(metas[0]?.text || '').trim()
    return [{ title: title0, frames: allFrames, sceneText: st0 || stFromRows }]
  }

  if (metaCount > 1 && list.length > metaCount) {
    const out = list.slice(0, metaCount).map((x) => ({ ...x, frames: [...x.frames] }))
    for (const ex of list.slice(metaCount)) {
      const last = out[metaCount - 1]
      last.frames.push(...ex.frames)
      if (ex.sceneText) {
        last.sceneText = last.sceneText ? `${last.sceneText}\n\n${ex.sceneText}` : ex.sceneText
      }
    }
    return out
  }

  return list
}

const buildFullContentFromPipeline = () => {
  const themeName = scene.value?.theme_name || '（未关联主题）'
  const boardName = scene.value?.name || '（未命名分镜）'
  const storyNode = findPipelineNodeByName('故事描述')
  const storyData = storyNode?.outputText ? parseStoryDescriptionDisplay(storyNode.outputText) : null
  const storyText = storyData?.story ? String(storyData.story) : ''
  const sceneMetas = getSceneListForFullContent()
  const rawFrameScenes = getFrameScenesForFullContent()
  const frameScenes = mergeFrameScenesForFullContent(rawFrameScenes, sceneMetas)
  const ts = Date.now()
  const scenes = frameScenes.map((fs, si) => {
    const sm = sceneMetas[si] || {}
    const title = String(fs.title || sm.title || `场景${si + 1}`).trim() || `场景${si + 1}`
    const sceneText = String(sm.text || fs.sceneText || '').trim()
    const shots = (fs.frames || []).map((fr, fi) => {
      const shotText = String(fr.description || '').trim()
      return {
        id: `fcg-sh-${ts}-${si}-${fi}`,
        shotText,
        comicDesc: '',
        animDesc: '',
      }
    })
    return {
      id: `fcg-sc-${ts}-${si}`,
      title,
      sceneText,
      shots,
    }
  })
  if (!scenes.length && sceneMetas.length) {
    return {
      themeName,
      boardName,
      storyText,
      scenes: sceneMetas.map((sm, si) => ({
        id: `fcg-sc-${ts}-${si}`,
        title: String(sm.title || `场景${si + 1}`),
        sceneText: String(sm.text || ''),
        shots: [{ id: `fcg-sh-${ts}-${si}-0`, shotText: '', comicDesc: '', animDesc: '' }],
      })),
    }
  }
  return { themeName, boardName, storyText, scenes }
}

/** 进入完整内容节点时合并：画面主述等用上游流水线最新稿，已保存的漫画/动画提示词按场景·画面下标保留 */
const mergeFullContentGenPreservePrompts = (fresh, stored) => {
  if (!fresh || !stored?.scenes?.length) return fresh
  const flat = []
  for (const osc of stored.scenes) {
    const row = osc.shots ?? osc.frames ?? osc.画面
    const arr = Array.isArray(row) ? row : []
    for (const osh of arr) {
      flat.push({
        comicDesc: String(osh?.comicDesc ?? osh?.comic ?? osh?.漫画 ?? '').trim(),
        animDesc: String(osh?.animDesc ?? osh?.anim ?? osh?.animation ?? osh?.动画 ?? '').trim(),
      })
    }
  }
  let idx = 0
  const scenes = (fresh.scenes || []).map((sc) => ({
    ...sc,
    shots: (sc.shots || []).map((sh) => {
      const p = flat[idx++]
      const comicDesc = p?.comicDesc || String(sh.comicDesc || '').trim()
      const animDesc = p?.animDesc || String(sh.animDesc || '').trim()
      return { ...sh, comicDesc, animDesc }
    }),
  }))
  return { ...fresh, scenes }
}

const unwrapFullContentJsonRoot = (o) => {
  if (!o || typeof o !== 'object') return null
  if (Array.isArray(o.scenes)) return o
  for (const k of ['result', 'data', 'output', 'fullContent', 'payload']) {
    const inner = o[k]
    if (inner && typeof inner === 'object' && Array.isArray(inner.scenes)) return inner
  }
  return null
}

const normalizeFullContentGenFromStored = (o) => {
  const root = unwrapFullContentJsonRoot(o) || (o && typeof o === 'object' && Array.isArray(o.scenes) ? o : null)
  if (!root || !Array.isArray(root.scenes)) return null
  return {
    themeName: String(root.themeName || ''),
    boardName: String(root.boardName || ''),
    storyText: String(root.storyText || ''),
    scenes: root.scenes.map((sc, si) => {
      const shotsRaw = sc.shots ?? sc.frames ?? sc.画面
      const shotsArr = Array.isArray(shotsRaw) ? shotsRaw : []
      return {
        id: sc.id || `fcg-sc-r-${si}`,
        title: String(sc.title || sc.name || `场景${si + 1}`),
        sceneText: String(sc.sceneText || sc.text || ''),
        shots: shotsArr.map((sh, fi) => {
          const comicDesc = String(sh.comicDesc ?? sh.comic ?? sh.漫画 ?? '')
          const animDesc = String(sh.animDesc ?? sh.anim ?? sh.animation ?? sh.动画 ?? '')
          let shotText = String(sh.shotText ?? sh.frameText ?? sh.description ?? sh.主述 ?? '').trim()
          if (!shotText && (comicDesc || animDesc)) {
            if (comicDesc && animDesc && comicDesc === animDesc) shotText = comicDesc
            else shotText = comicDesc || animDesc
          }
          return {
            id: sh.id || `fcg-sh-r-${si}-${fi}`,
            shotText,
            comicDesc,
            animDesc,
          }
        }),
      }
    }),
  }
}

const syncFullContentFromNodeOutput = (node) => {
  const raw = String(node?.outputText || '').trim()
  if (!raw) return false
  const blob = extractJsonObjectString(raw)
  if (!blob) return false
  try {
    const o = JSON.parse(blob)
    const norm = normalizeFullContentGenFromStored(o)
    if (norm) {
      node.fullContentGen = norm
      return true
    }
  } catch {
    /* ignore */
  }
  return false
}

const syncFullContentToOutput = (node) => {
  const f = node?.fullContentGen
  if (!f || !node) return
  node.outputText = JSON.stringify(
    {
      version: 1,
      themeName: f.themeName,
      boardName: f.boardName,
      storyText: f.storyText,
      scenes: f.scenes.map((sc) => ({
        id: sc.id,
        title: sc.title,
        sceneText: sc.sceneText,
        shots: (sc.shots || []).map((sh) => ({
          id: sh.id,
          shotText: sh.shotText || '',
          comicDesc: sh.comicDesc || '',
          animDesc: sh.animDesc || '',
        })),
      })),
    },
    null,
    2,
  )
}

const ensureFullContentGenState = (node) => {
  if (!node || node.name !== '完整内容生成') return
  if (node.fullContentAiModifyText === undefined) node.fullContentAiModifyText = ''
  if (node.fullContentAiTarget === undefined) node.fullContentAiTarget = null

  if (node.completed) {
    if (!node.fullContentGen) {
      syncFullContentFromNodeOutput(node)
    }
    return
  }

  let stored = null
  const raw = String(node.outputText || '').trim()
  if (raw) {
    try {
      const blob = extractJsonObjectString(raw)
      if (blob) {
        const o = JSON.parse(blob)
        stored = normalizeFullContentGenFromStored(o)
      }
    } catch {
      /* ignore */
    }
  }

  const fresh = buildFullContentFromPipeline()
  if (!fresh.scenes?.length) {
    node.fullContentGen = stored?.scenes?.length ? stored : fresh
  } else {
    node.fullContentGen = mergeFullContentGenPreservePrompts(fresh, stored)
  }
  syncFullContentToOutput(node)
}

/** 单次 API 响应示例：scenes 长度必须为 1；shots 条数须等于本场景画面数（复制到提示词管理时用此形状） */
const fullContentBatchJsonFormatExample = `{
  "version": 1,
  "scenes": [
    {
      "title": "场景标题（可与当前消息中的场景一致或略写）",
      "sceneText": "（可选）",
      "shots": [
        {
          "shotText": "画面1 主述（可与消息中主述一致）",
          "comicDesc": "该画面对应的漫画/静帧生成提示词",
          "animDesc": "该画面对应的动画/镜头运动提示词"
        },
        {
          "shotText": "画面2 主述",
          "comicDesc": "…",
          "animDesc": "…"
        }
      ]
    }
  ]
}`

/** 整段复制到「提示词管理」：任务说明 + 与 fullContentBatchJsonFormatExample 一致的 JSON 样例 */
const fullContentPromptSpecForTemplate = [
  '【完整内容生成】运行页已改为「按场景分批请求」：每次用户消息里只有<strong>一个</strong>场景的画面主述，模型应返回 scenes 长度=1 的 JSON。',
  '',
  '任务：根据【已评审画面】中<strong>本消息所列该场景</strong>的各条主述（及系统附带的「角色长相」节选），为该场景下每一幅画面生成 comicDesc（漫画/静帧提示词）与 animDesc（动画/运镜提示词）。',
  '只输出一段合法 JSON；禁止 markdown 代码块；禁止「以下是」等前后说明。',
  '建议含 "version": 1；**"scenes" 数组长度必须为 1**；其下 shots（或 frames）顺序 = 该场景画面1、2…，与消息一致。',
  '每个 shot 须有 shotText（可与主述一致或略写）、comicDesc、animDesc；可用别名键 comic、anim、animation。',
  '',
  '下方示例即为<strong>单次</strong>应返回的完整 JSON（勿在一次响应里放多个场景对象）。',
  fullContentBatchJsonFormatExample,
].join('\n')

const copyFullContentPromptSpecForConfig = async () => {
  try {
    await navigator.clipboard.writeText(fullContentPromptSpecForTemplate)
    ElMessage.success('已复制全文，可粘贴到提示词管理')
  } catch {
    ElMessage.error('复制失败')
  }
}

/** 单场景请求：只附带第 sceneIndex0+1 个场景的画面主述 */
const buildFullContentBatchPromptContextForScene = (sceneIndex0) => {
  const f = currentNode.value?.fullContentGen
  if (!f?.scenes?.[sceneIndex0]) return ''
  const sc = f.scenes[sceneIndex0]
  const lines = []
  lines.push('【已评审画面 · 本请求仅含下列一个场景】')
  const inner = stripLeadingSceneIndexForFcg(sc.title, sceneIndex0 + 1) || `场景${sceneIndex0 + 1}`
  lines.push(`【场景${sceneIndex0 + 1}：${inner}】`)
  ;(sc.shots || []).forEach((sh, fi) => {
    lines.push(`  · 画面${fi + 1} 主述：${String(sh.shotText || '').trim() || '（无）'}`)
  })
  return lines.join('\n')
}

const FULL_CONTENT_PER_SCENE_JSON_RULE =
  '【输出要求 · 本请求为分批之一】请只输出一段合法 JSON（禁止 markdown 围栏、禁止 JSON 前后说明文字）。' +
  '建议含 "version": 1；**顶层 "scenes" 数组长度必须为 1**，且唯一元素须对应当前消息中的这一场景。' +
  '该场景下 "shots"（或 frames）条数须与上方「画面」条数一致、顺序一致。' +
  '每条含 shotText（可与主述一致）、comicDesc、animDesc。'

/**
 * 将单场景解析结果合并进节点（只更新指定场景的 comicDesc/animDesc，保留原有 shotText）。
 * @returns {{ ok: boolean, detail?: string }}
 */
const mergeFullContentOneSceneFromParsed = (node, sceneIndex0, parsedRoot) => {
  const norm = normalizeFullContentGenFromStored(parsedRoot)
  if (!norm?.scenes?.length) return { ok: false, detail: '无法解析为完整内容 JSON（需含 scenes）' }
  if (norm.scenes.length > 1) {
    ElMessage.warning(`场景 ${sceneIndex0 + 1}：模型返回了 ${norm.scenes.length} 个 scenes，仅合并第一项`)
  }
  const block = norm.scenes[0]
  const tgtScene = node?.fullContentGen?.scenes?.[sceneIndex0]
  if (!tgtScene) return { ok: false, detail: '本地无对应场景' }
  const srcShots = block.shots || []
  if (!Array.isArray(srcShots) || srcShots.length === 0) {
    return { ok: false, detail: '模型未返回 shots/frames' }
  }
  const dst = tgtScene.shots || []
  if (srcShots.length !== dst.length) {
    ElMessage.warning(
      `场景 ${sceneIndex0 + 1}：模型返回 ${srcShots.length} 条画面，当前表 ${dst.length} 条，将按较短边合并`,
    )
  }
  const n = Math.min(srcShots.length, dst.length)
  const newShots = dst.map((sh, fi) => {
    if (fi >= n) return sh
    const src = srcShots[fi]
    const comicDesc = String(src?.comicDesc ?? src?.comic ?? src?.漫画 ?? '').trim()
    const animDesc = String(src?.animDesc ?? src?.anim ?? src?.animation ?? src?.动画 ?? '').trim()
    return {
      ...sh,
      shotText: String(sh.shotText || '').trim(),
      comicDesc: comicDesc || String(sh.comicDesc || '').trim(),
      animDesc: animDesc || String(sh.animDesc || '').trim(),
    }
  })
  node.fullContentGen = {
    ...node.fullContentGen,
    scenes: node.fullContentGen.scenes.map((sc, si) =>
      si === sceneIndex0 ? { ...sc, shots: newShots } : sc,
    ),
  }
  return { ok: true }
}

/** 画面评审「优化分镜」等键，写回时与 parseFrameReviewJson 读取一致 */
const FRAME_REVIEW_OPT_KEYS = ['优化分镜', 'optimizedScenes', 'framesReview']

/**
 * 解析可读「【场景】\\n  · 画面N：描述」块为 { title, frames }[]
 * （与 formatReviewPanePlainText 中带 frames 的场景条一致）
 */
/** 从场景块正文解析「· 画面N：」列表；支持描述跨多行（直到下一幅画面或场景标题） */
const parseFrameReviewBodyToFrames = (body) => {
  const text = String(body ?? '').trim()
  if (!text) return []
  const lines = text.split(/\r?\n/)
  const head = /^\s*(?:[·•．・]|-\s*|－\s*)画面\s*\d+\s*[：:]|^\s*画面\s*\d+\s*[：:]/
  const shotLine =
    /^\s*(?:[·•．・]|-\s*|－\s*)画面\s*(\d+)\s*[：:]\s*(.*)$/
  const shotLineLoose = /^\s*画面\s*(\d+)\s*[：:]\s*(.*)$/
  const frames = []
  let buf = []
  const flush = () => {
    if (!buf.length) return
    const desc = buf.join('\n').trim()
    if (desc) frames.push({ description: desc })
    buf = []
  }
  for (const line of lines) {
    const sm = line.match(shotLine) || line.match(shotLineLoose)
    if (sm) {
      flush()
      buf.push(String(sm[2] ?? '').trim())
    } else if (buf.length && !head.test(line)) {
      buf.push(line)
    }
  }
  flush()
  return frames
}

const parseFrameReviewBracketBlocks = (raw) => {
  const str = String(raw ?? '').trim()
  if (!str || !str.includes('【')) return null
  const chunks = str.split(/(?=【[^】]+】)/).filter((c) => c.trim())
  if (!chunks.length) return null
  const scenes = []
  for (const chunk of chunks) {
    const c = chunk.trim()
    const m = c.match(/^【([^】]+)】\s*\r?\n([\s\S]*)$/)
    let title = ''
    let body = ''
    if (m) {
      title = m[1].trim()
      body = (m[2] || '').trim()
    } else {
      const m2 = c.match(/^【([^】]+)】\s*([\s\S]*)$/s)
      if (!m2) continue
      title = m2[1].trim()
      body = (m2[2] || '').trim()
    }
    const frames = parseFrameReviewBodyToFrames(body)
    if (!frames.length && body) frames.push({ description: body })
    scenes.push({ title: title || `场景${scenes.length + 1}`, frames })
  }
  return scenes.length ? scenes : null
}

/** 草稿为整段 JSON（含优化分镜或仅 scenes）时直接还原，避免仅依赖可读块往返 */
const tryParseFrameReviewOptimizedScenesFromJson = (s) => {
  const blob = extractStructuredJsonBlob(String(s))
  if (!blob) return null
  try {
    const o = JSON.parse(blob)
    if (!o || typeof o !== 'object') return null
    const inner = unwrapFrameReviewRoot(o)
    const scenes = tryOptimizedScenesFromFrameReviewRoot(inner)
    return scenes.length ? scenes : null
  } catch {
    return null
  }
}

/** 将「修改后」可读正文还原为优化分镜结构（仅 title + frames.description） */
const parseFrameOptimizedPlainToScenes = (plain) => {
  const s = String(plain ?? '').trim()
  if (!s) return []
  if (/^\s*\{/.test(s)) {
    const fromOpt = tryParseFrameReviewOptimizedScenesFromJson(s)
    if (fromOpt?.length) return fromOpt
    const parsedFd = parseFrameDecompositionJson(s)
    if (parsedFd?.scenes?.length) {
      return parsedFd.scenes.map((sc, i) => ({
        title: String(sc.title || '').trim() || `场景${i + 1}`,
        frames: (sc.frames || []).map((fr) => ({
          description: String(fr.description || '').trim(),
        })),
      }))
    }
  }
  const blocks = parseFrameReviewBracketBlocks(s)
  if (blocks?.length) return blocks
  return [{ title: '场景1', frames: [{ description: s }] }]
}

const patchOptimizedScenesOnFrameReviewObject = (o, scenes) => {
  if (!o || typeof o !== 'object' || Array.isArray(o)) return
  const payload = scenes.map((sc, si) => ({
    title: String(sc.title || '').trim() || `场景${si + 1}`,
    frames: (sc.frames || []).map((fr) => ({
      description: String(fr.description || '').trim(),
    })),
  }))
  const newShape =
    '评审结论' in o ||
    '总评' in o ||
    'conclusion' in o ||
    'summary' in o ||
    '问题清单及修改建议' in o ||
    '原内容' in o ||
    '修改后' in o ||
    'modified' in o ||
    'revised' in o ||
    'after' in o
  if (newShape) {
    o.修改后 = { scenes: payload }
  }
  let touched = false
  for (const k of FRAME_REVIEW_OPT_KEYS) {
    if (Object.prototype.hasOwnProperty.call(o, k)) {
      o[k] = payload
      touched = true
    }
  }
  if (!newShape && !touched) o.优化分镜 = payload
}

/** 从已解析的画面评审根对象取出优化分镜（与 parseFrameReviewJson / 后端解析一致） */
const readOptimizedScenesFromFrameReviewRoot = (root) => {
  const scenes = tryOptimizedScenesFromFrameReviewRoot(root)
  return scenes.length ? scenes : null
}

const sameOptimizedScenesShape = (a, b) => {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false
  return a.every((sc, i) => (sc.frames || []).length === (b[i]?.frames || []).length)
}

const flattenOptimizedDescriptions = (scenes) =>
  (scenes || []).flatMap((sc) => (sc.frames || []).map((f) => String(f?.description ?? '').trim()))

/**
 * 以当前 JSON 里的优化分镜为「骨架」，避免可读稿解析失败时画面变少/内容被替换成一整段。
 * - 场景数与各场景下画面数与解析结果一致 → 采用解析结果（含标题与描述）
 * - 总画面数一致但场景分组不一致 → 按现有分组顺序，把解析出的描述按顺序填入
 * - 解析出的画面更多 → 采用解析结果（用户扩写）
 * - 解析出的画面更少 → 按遍历顺序把解析到的描述写回骨架；未覆盖的格子保留原描述（避免改几个字就整表被拒）
 */
const reconcileFrameReviewOptimizedScenes = (existing, parsed) => {
  if (!parsed?.length) return existing
  if (!existing?.length) return parsed
  if (sameOptimizedScenesShape(existing, parsed)) return parsed
  const fe = flattenOptimizedDescriptions(existing)
  const fp = flattenOptimizedDescriptions(parsed)
  if (fp.length === fe.length) {
    let idx = 0
    return existing.map((sc) => ({
      title: sc.title,
      frames: (sc.frames || []).map(() => {
        const d = fp[idx++]
        return { description: d !== undefined ? d : '' }
      }),
    }))
  }
  if (fp.length > fe.length) return parsed
  if (fp.length > 0) {
    let idx = 0
    return existing.map((sc) => ({
      title: sc.title,
      frames: (sc.frames || []).map((fr) => {
        const oldD = String(fr?.description ?? '').trim()
        if (idx < fp.length) {
          const d = fp[idx++]
          return { description: d !== undefined ? String(d) : oldD }
        }
        return { description: oldD }
      }),
    }))
  }
  return existing
}

/** 分块编辑：直接用场景/画面结构写回「优化分镜」，不经过可读稿解析 */
const applyFrameReviewOptimizedStructuredToOutput = (node, scenes) => {
  if (!node || node.name !== '画面评审') return false
  const raw = String(node.outputText || '').trim()
  if (!raw) return false
  const blob = extractStructuredJsonBlob(raw)
  if (!blob) return false
  try {
    const root = JSON.parse(blob)
    if (!root || typeof root !== 'object') return false
    if (!Array.isArray(scenes) || !scenes.length) return false
    const payload = scenes.map((sc, si) => ({
      title: String(sc.title || '').trim() || `场景${si + 1}`,
      frames: (sc.frames || []).map((fr) => ({
        description: String(fr?.description ?? '').trim(),
      })),
    }))
    patchOptimizedScenesOnFrameReviewObject(root, payload)
    node.outputText = JSON.stringify(root, null, 2)
    return true
  } catch {
    return false
  }
}

/** 可读「修改后」写回根 JSON 的优化分镜字段（存储仍为 JSON） */
const applyFrameReviewOptimizedDraftToOutput = (node, draftPlain) => {
  if (!node || node.name !== '画面评审') return false
  const raw = String(node.outputText || '').trim()
  if (!raw) return false
  const blob = extractStructuredJsonBlob(raw)
  if (!blob) return false
  try {
    const root = JSON.parse(blob)
    if (!root || typeof root !== 'object') return false
    const existing = readOptimizedScenesFromFrameReviewRoot(root)
    const parsed = parseFrameOptimizedPlainToScenes(String(draftPlain ?? ''))
    if (!parsed.length) {
      return true
    }
    const merged = reconcileFrameReviewOptimizedScenes(existing, parsed)
    if (!merged?.length) {
      return true
    }
    const fp = flattenOptimizedDescriptions(parsed)
    const fe = flattenOptimizedDescriptions(existing)
    if (existing?.length && fp.length > 0 && fp.length < fe.length) {
      ElMessage.info(
        '已按顺序合并可识别的画面描述；未匹配到的条目保留原内容。若要删减画面或改场景结构，请粘贴含「优化分镜」的完整 JSON 后再保存。',
      )
    }
    patchOptimizedScenesOnFrameReviewObject(root, merged)
    node.outputText = JSON.stringify(root, null, 2)
    return true
  } catch {
    return false
  }
}

const frameReviewOptimizedDraft = ref('')
/** 画面评审「修改后」分块编辑：{ title, frames: [{ description }] }[] */
const frameReviewOptimizedEditScenes = ref([])
const frameReviewRevising = ref(false)
const frameReviewEditSessionBaseline = ref('')
/** 进入编辑时的场景快照，用于取消恢复 */
const frameReviewEditSessionScenesBaseline = ref(null)

const hydrateFrameReviewEditScenesFromUpstreamFrameDecomp = () => {
  const fdNode = findPipelineNodeByName('画面分解')
  const rawUp = String(fdNode?.outputText ?? '').trim()
  if (!rawUp) return []
  const fd = parseFrameDecompositionJson(rawUp)
  if (!fd?.scenes?.length) return []
  return fd.scenes.map((sc, i) => ({
    title: String(sc.title || '').trim() || `场景${i + 1}`,
    frames: (sc.frames || []).length
      ? sc.frames.map((f) => ({ description: String(f.description || '').trim() }))
      : [{ description: '' }],
  }))
}

const syncFrameReviewOptimizedDraftFromOutput = () => {
  const n = currentNode.value
  if (!n || n.name !== '画面评审') return
  const data = parseFrameReviewJson(String(n.outputText ?? ''))
  let scenes = data?.scenes?.length ? data.scenes : []
  if (!scenes.length) {
    scenes = hydrateFrameReviewEditScenesFromUpstreamFrameDecomp()
  }
  if (!scenes.length) {
    frameReviewOptimizedDraft.value = ''
    frameReviewOptimizedEditScenes.value = []
    return
  }
  frameReviewOptimizedEditScenes.value = scenes.map((sc) => ({
    title: sc.title || '',
    frames: (sc.frames || []).length
      ? sc.frames.map((f) => ({ description: String(f.description || '') }))
      : [{ description: '' }],
  }))
  frameReviewOptimizedDraft.value = formatOptimizedScenesAsPlain(frameReviewOptimizedEditScenes.value)
}

/** 与「修改后」scenes 同构的可编辑列表（按场景对比 / 单场景重生成） */
const sceneReviewRevisedEditScenes = ref([])
/** 进入结构化编辑时的 scenes 快照，用于取消恢复 */
const sceneReviewEditSessionScenesBaseline = ref([])
const sceneReviewRevising = ref(false)
/** 结构化编辑：进入编辑时整表可读稿基线 */
const sceneReviewEditSessionStructuredPlain = ref('')
/** 对比区按场景直接改「评审后」正文（标题展示在「场景 N：…」抬头） */
const sceneReviewInlineEditIndex = ref(null)
const sceneReviewInlineAfterDraft = ref('')
/** 进入行内编辑时锁定的短标题，保存时写入 JSON 的 title，正文不含【】行 */
const sceneReviewInlineHeadlineSnapshot = ref('')

const ensureSceneReviewEditScenesHydrated = () => {
  if (sceneReviewRevisedEditScenes.value.length) return
  const n = currentNode.value
  const pr = tryParseSceneReviewJson(String(n?.outputText ?? ''))
  if (pr.ok && pr.data.revisedScenes?.length) {
    sceneReviewRevisedEditScenes.value = pr.data.revisedScenes.map((s, i) => ({
      id: s.id || `sr-e-${i}`,
      title: s.title,
      text: String(s.text ?? ''),
      updatedAt: s.updatedAt,
    }))
    return
  }
  const before = sceneReviewBeforeScenesList.value
  if (before.length) {
    sceneReviewRevisedEditScenes.value = before.map((b, i) => ({
      id: `sr-e-${i}-${Date.now()}`,
      title: b.title,
      text: b.text,
    }))
  }
}

/** 首行【标题】与 title 字段抽到抬头，框内仅正文 */
const splitSceneHeadlineAndBody = (sc) => {
  const titleField = String(sc?.title ?? '').trim()
  const raw = String(sc?.text ?? '')
  const m = raw.match(/^\s*【([^】]+)】\s*\r?\n([\s\S]*)$/)
  if (m) {
    return { headline: String(m[1] || '').trim(), body: String(m[2] || '').trim() }
  }
  const m2 = raw.match(/^\s*【([^】]+)】\s*$/)
  if (m2) {
    return { headline: String(m2[1] || '').trim(), body: '' }
  }
  if (titleField) return { headline: titleField, body: raw.trim() }
  return { headline: '', body: raw.trim() }
}

const startSceneReviewInlineEdit = (sceneIndex) => {
  if (isCompletedNodeReadonly.value) return
  const rows = sceneReviewPerSceneRows.value
  const row = rows[sceneIndex]
  if (!row) return
  ensureSceneReviewEditScenesHydrated()
  while (sceneReviewRevisedEditScenes.value.length <= sceneIndex) {
    const bi = sceneReviewRevisedEditScenes.value.length
    const b = sceneReviewBeforeScenesList.value[bi]
    sceneReviewRevisedEditScenes.value.push({
      id: `sr-e-${Date.now()}-${bi}`,
      title: b?.title || `场景${bi + 1}`,
      text: b?.text ?? '',
    })
  }
  sceneReviewInlineEditIndex.value = sceneIndex
  sceneReviewInlineHeadlineSnapshot.value = row.sceneHeadline || ''
  sceneReviewInlineAfterDraft.value = row.afterBody ?? ''
}

const cancelSceneReviewInlineEdit = () => {
  sceneReviewInlineEditIndex.value = null
}

const saveSceneReviewInlineEdit = () => {
  const n = currentNode.value
  if (!n || n.name !== '场景评审') return
  if (isCompletedNodeReadonly.value) return
  const i = sceneReviewInlineEditIndex.value
  if (i == null) return
  ensureSceneReviewEditScenesHydrated()
  while (sceneReviewRevisedEditScenes.value.length <= i) {
    const bi = sceneReviewRevisedEditScenes.value.length
    const b = sceneReviewBeforeScenesList.value[bi]
    sceneReviewRevisedEditScenes.value.push({
      id: `sr-e-${Date.now()}-${bi}`,
      title: b?.title || `场景${bi + 1}`,
      text: b?.text ?? '',
    })
  }
  const sc = sceneReviewRevisedEditScenes.value[i]
  const h = String(sceneReviewInlineHeadlineSnapshot.value || '').trim()
  sc.title = h || String(sc.title || '').trim() || `场景${i + 1}`
  sc.text = String(sceneReviewInlineAfterDraft.value ?? '')
  sc.updatedAt = new Date().toISOString()
  if (!applySceneReviewStructuredToOutput(n, sceneReviewRevisedEditScenes.value)) {
    ElMessage.error('写回场景评审 JSON 失败')
    return
  }
  sceneReviewInlineEditIndex.value = null
  persistState()
  ElMessage.success('已保存')
}

const enterSceneReviewEdit = () => {
  if (isCompletedNodeReadonly.value) return
  sceneReviewInlineEditIndex.value = null
  ensureSceneReviewEditScenesHydrated()
  if (!sceneReviewRevisedEditScenes.value.length) {
    sceneReviewRevisedEditScenes.value = [{ id: `sr-e-${Date.now()}`, title: '场景1', text: '' }]
  }
  sceneReviewEditSessionStructuredPlain.value = formatSceneReviewScenesAsPlain(sceneReviewRevisedEditScenes.value)
  sceneReviewEditSessionScenesBaseline.value = JSON.parse(JSON.stringify(sceneReviewRevisedEditScenes.value))
  sceneReviewRevising.value = true
}

const cancelSceneReviewEdit = () => {
  sceneReviewRevisedEditScenes.value = JSON.parse(JSON.stringify(sceneReviewEditSessionScenesBaseline.value || []))
  sceneReviewRevising.value = false
  sceneReviewInlineEditIndex.value = null
}

const saveSceneReviewRevised = () => {
  if (isCompletedNodeReadonly.value) return
  const n = currentNode.value
  if (!n || n.name !== '场景评审') return
  if (!applySceneReviewStructuredToOutput(n, sceneReviewRevisedEditScenes.value)) {
    ElMessage.error('保存失败：场景评审根 JSON 无法解析，请检查模型输出')
    return
  }
  persistState()
  sceneReviewRevising.value = false
  sceneReviewInlineEditIndex.value = null
  syncSceneReviewRevisedDraftFromOutput()
  ElMessage.success('已定稿并保存到本节点输出')
}

/** 编辑态：当前草稿相对「打开编辑时」的文本差异（右侧片段：绿=新增，黑=未改） */
const sceneReviewSessionDiff = computed(() => {
  if (!sceneReviewRevising.value) return { left: [], right: [] }
  const cur = formatSceneReviewScenesAsPlain(sceneReviewRevisedEditScenes.value)
  return buildReviewTextDiff(sceneReviewEditSessionStructuredPlain.value, cur)
})

/** 编辑态「已删除」区：仅当相对基线有删减时展示，内容与 diff 左栏语义一致 */
const sceneReviewSessionRemovalSpans = computed(() => {
  const left = sceneReviewSessionDiff.value.left
  if (!left.length || !left.some((s) => s.op === 'before')) return []
  return left
})

const sceneReviewView = computed(() => {
  if (!isSceneReviewNode.value) return null
  const up = getImmediateUpstreamOutput()
  const upstreamText = (up?.text || '').trim()
  const upstreamPreview = upstreamText ? (formatReviewPanePlainText(upstreamText) || upstreamText) : ''
  const pr = tryParseSceneReviewJson(currentOutputText.value)
  if (pr.ok) {
    return {
      mode: 'parsed',
      data: pr.data,
      upstreamPreview,
      failureReason: null,
    }
  }
  return {
    mode: 'parse_failed',
    data: null,
    upstreamPreview,
    failureReason: pr.reason,
  }
})

/** 评审前各场景卡片：优先模型「原内容」中的 scenes，否则用上游场景分解 */
const sceneReviewBeforeScenesList = computed(() => {
  if (!isSceneReviewNode.value) return []
  const raw = String(currentOutputText.value ?? '').trim()
  const pr = tryParseSceneReviewJson(raw)
  if (!pr.ok) return []
  const oStr = pr.data.original?.trim() ?? ''
  if (oStr) {
    const p = parseSceneDecompositionJson(oStr)
    if (p?.scenes?.length) return p.scenes.map((sc, si) => normalizeSdScene(sc, si))
    const ob = extractJsonObjectString(oStr)
    if (ob) {
      try {
        const jo = JSON.parse(ob)
        const list = jo.scenes ?? jo.场景列表
        if (Array.isArray(list) && list.length) {
          return list.map((sc, si) => normalizeSdScene(sc, si))
        }
      } catch {
        /* ignore */
      }
    }
  }
  const up = getImmediateUpstreamOutput()
  const upText = (up?.text || '').trim()
  if (!upText) return []
  const p2 = parseSceneDecompositionJson(upText)
  return p2?.scenes?.length ? p2.scenes.map((sc, si) => normalizeSdScene(sc, si)) : []
})

const sceneReviewPerSceneRows = computed(() => {
  if (!isSceneReviewNode.value) return []
  const pr = tryParseSceneReviewJson(currentOutputText.value)
  if (!pr.ok) return []
  const before = sceneReviewBeforeScenesList.value
  const afterSrc = sceneReviewRevisedEditScenes.value.length
    ? sceneReviewRevisedEditScenes.value
    : pr.data.revisedScenes || []
  const n = Math.max(before.length, afterSrc.length, 1)
  const rows = []
  for (let i = 0; i < n; i++) {
    const b = before[i] || { title: '', text: '' }
    const a = afterSrc[i] || { title: '', text: '' }
    const bSplit = splitSceneHeadlineAndBody(b)
    const aSplit = splitSceneHeadlineAndBody(a)
    const sceneHeadline = aSplit.headline || bSplit.headline
    const bPlain = (bSplit.body || '').trim() || '（无）'
    const aPlain = (aSplit.body || '').trim() || '（无）'
    rows.push({
      index: i,
      sceneHeadline,
      beforeBody: bSplit.body,
      afterBody: aSplit.body,
      diff: buildReviewTextDiff(bPlain, aPlain),
      beforePlain: bPlain,
      afterPlain: aPlain,
    })
  }
  return rows
})

/** 模型未填「原内容」时，评审前列表来自上游场景分解 */
const sceneReviewUsedUpstreamAsDiffBase = computed(() => {
  const v = sceneReviewView.value
  if (!v || v.mode !== 'parsed') return false
  return !String(v.data?.original || '').trim() && !!String(v.upstreamPreview || '').trim()
})

const sceneReviewShowDiffLegend = computed(() => {
  if (!isSceneReviewNode.value || sceneReviewView.value?.mode !== 'parsed') return false
  if (sceneReviewRevising.value) return true
  return sceneReviewPerSceneRows.value.some((r) => r.beforePlain?.trim() || r.afterPlain?.trim())
})

/**
 * 从节点 output 同步「修改后」scenes 到可编辑列表。
 */
const syncSceneReviewRevisedDraftFromOutput = () => {
  const n = currentNode.value
  if (!n || n.name !== '场景评审') return
  const pr = tryParseSceneReviewJson(String(n.outputText ?? ''))
  if (pr.ok && pr.data.revisedScenes?.length) {
    sceneReviewRevisedEditScenes.value = pr.data.revisedScenes.map((s, i) => ({
      id: s.id || `sr-e-${i}`,
      title: s.title,
      text: String(s.text ?? ''),
      updatedAt: s.updatedAt,
    }))
  } else {
    sceneReviewRevisedEditScenes.value = []
  }
}

watch(
  () => {
    const n = currentNode.value
    return n?.name === '场景评审' ? String(n.outputText ?? '') : null
  },
  (t) => {
    if (t === null) return
    if (sceneReviewRevising.value) return
    if (sceneReviewInlineEditIndex.value != null) return
    syncSceneReviewRevisedDraftFromOutput()
  },
  { immediate: true },
)

watch(
  () => {
    const n = currentNode.value
    return n?.name === '画面评审' ? String(n.outputText ?? '') : null
  },
  (t) => {
    if (t === null) return
    if (frameReviewRevising.value) return
    syncFrameReviewOptimizedDraftFromOutput()
  },
  { immediate: true },
)

watch(activeNodeIndex, (n, o) => {
  sceneReviewRevising.value = false
  frameReviewRevising.value = false
  sceneReviewInlineEditIndex.value = null
  const wasFrameReview = (idx) => idx != null && nodes.value[idx]?.name === '画面评审'
  if (wasFrameReview(o) && !wasFrameReview(n)) {
    frameReviewOptimizedDraft.value = ''
    frameReviewOptimizedEditScenes.value = []
  }
  if (o != null && nodes.value[o]?.name === '场景分解') {
    const prev = nodes.value[o]
    const editId = sceneDecompEditingId.value
    if (editId && prev.sceneDecomposition && normalizeSceneDecompSceneById(prev.sceneDecomposition, editId)) {
      syncSceneDecompToOutput(prev)
      persistState()
    }
  }
  if (o != null && nodes.value[o]?.name === '画面分解') {
    const prev = nodes.value[o]
    const editId = frameDecompEditingId.value
    if (editId && prev.frameDecomposition && normalizeFrameDecompSceneById(prev.frameDecomposition, editId)) {
      syncFrameDecompToOutput(prev)
      persistState()
    }
  }
  frameDecompEditingId.value = null
  sceneDecompEditingId.value = null
})

const sceneReviewParseToastKey = ref('')
watch(
  () => {
    if (!isSceneReviewNode.value) return null
    const v = sceneReviewView.value
    if (!v || v.mode !== 'parse_failed' || !v.failureReason) return null
    const out = currentOutputText.value || ''
    return `${v.failureReason}|${out.length}|${out.slice(0, 200)}`
  },
  (key) => {
    if (!key) return
    if (sceneReviewParseToastKey.value === key) return
    sceneReviewParseToastKey.value = key
    const v = sceneReviewView.value
    if (v?.failureReason) {
      ElMessage.warning({
        message: `场景评审无法结构化展示：${v.failureReason}`,
        duration: 9000,
        showClose: true,
      })
    }
  },
)

const storyDescriptionDisplayText = computed(() => {
  if (!isStoryDescriptionNode.value) return '暂无输出'
  const d = parseStoryDescriptionDisplay(currentOutputText.value)
  return d?.story ? d.story : '暂无输出'
})

const frameReviewData = computed(() => {
  if (!isFrameReviewNode.value) return null
  return parseFrameReviewJson(currentOutputText.value)
})

/** 画面评审对比：左侧「修改前」= 上游画面分解格式化为可读文本 */
const frameReviewDiffBasePlain = computed(() => {
  if (!isFrameReviewNode.value) return ''
  const up = getImmediateUpstreamOutput()
  const t = (up?.text || '').trim()
  if (!t) return ''
  return formatReviewPanePlainText(t) || t
})

const frameReviewDiffRevisedPlain = computed(() => {
  const scenes = frameReviewOptimizedEditScenes.value
  if (Array.isArray(scenes) && scenes.length) {
    return formatOptimizedScenesAsPlain(scenes)
  }
  const d = String(frameReviewOptimizedDraft.value ?? '').trim()
  if (!d) return ''
  return formatReviewPanePlainText(frameReviewOptimizedDraft.value) || d
})

const frameReviewDiff = computed(() => {
  if (!isFrameReviewNode.value || !frameReviewData.value) return { left: [], right: [] }
  return buildReviewTextDiff(frameReviewDiffBasePlain.value, frameReviewDiffRevisedPlain.value)
})

const frameReviewDiffHasBothSides = computed(() => {
  return !!(frameReviewDiffBasePlain.value.trim() || frameReviewDiffRevisedPlain.value.trim())
})

const enterFrameReviewEdit = () => {
  if (isCompletedNodeReadonly.value) return
  syncFrameReviewOptimizedDraftFromOutput()
  frameReviewEditSessionScenesBaseline.value = JSON.parse(JSON.stringify(frameReviewOptimizedEditScenes.value || []))
  frameReviewEditSessionBaseline.value = formatOptimizedScenesAsPlain(frameReviewOptimizedEditScenes.value || [])
  frameReviewRevising.value = true
}

const addFrameReviewShot = (sceneIndex) => {
  const rows = frameReviewOptimizedEditScenes.value
  if (!rows[sceneIndex]) return
  rows[sceneIndex].frames.push({ description: '' })
}

const removeFrameReviewShot = (sceneIndex, frameIndex) => {
  const sc = frameReviewOptimizedEditScenes.value[sceneIndex]
  if (!sc?.frames?.length) return
  if (sc.frames.length <= 1) {
    sc.frames[0].description = ''
    return
  }
  sc.frames.splice(frameIndex, 1)
}

const cancelFrameReviewEdit = () => {
  if (frameReviewEditSessionScenesBaseline.value) {
    frameReviewOptimizedEditScenes.value = JSON.parse(JSON.stringify(frameReviewEditSessionScenesBaseline.value))
  }
  frameReviewRevising.value = false
}

const saveFrameReviewOptimized = () => {
  if (isCompletedNodeReadonly.value) return
  const n = currentNode.value
  if (!n || n.name !== '画面评审') return
  if (!applyFrameReviewOptimizedStructuredToOutput(n, frameReviewOptimizedEditScenes.value)) {
    ElMessage.error('保存失败：画面评审输出 JSON 无法解析或无法写回「优化分镜」')
    return
  }
  persistState()
  frameReviewRevising.value = false
  frameReviewEditSessionScenesBaseline.value = null
  syncFrameReviewOptimizedDraftFromOutput()
  ElMessage.success('已保存优化分镜')
}

const frameReviewCurrentEditPlain = computed(() => formatOptimizedScenesAsPlain(frameReviewOptimizedEditScenes.value || []))

const frameReviewSessionDiff = computed(() => {
  if (!frameReviewRevising.value) return { left: [], right: [] }
  return buildReviewTextDiff(frameReviewEditSessionBaseline.value, frameReviewCurrentEditPlain.value)
})

const frameReviewSessionRemovalSpans = computed(() => {
  const left = frameReviewSessionDiff.value.left
  if (!left.length || !left.some((s) => s.op === 'before')) return []
  return left
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
  const maxSrc = Math.max(0, src.scrollHeight - src.clientHeight)
  const maxDst = Math.max(0, dst.scrollHeight - dst.clientHeight)
  if (maxSrc <= 0 && maxDst <= 0) return
  const ratio = maxSrc > 0 ? src.scrollTop / maxSrc : 0
  reviewScrollSuppress.value = true
  if (maxDst > 0) {
    dst.scrollTop = Math.min(maxDst, Math.max(0, ratio * maxDst))
  }
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
  syncLocalStorageFromState()
  clearTimeout(pipelineSaveTimer)
  pipelineSaveTimer = setTimeout(() => {
    pipelineSaveTimer = null
    savePipelineToServer().catch((e) => {
      console.error(e)
      ElMessage.warning('流水线状态同步服务器失败（已保留在本机）')
    })
  }, 500)
}

/** 每次模型生成成功后立即写入本地并推送服务端，保证可随时从库中读到最新稿 */
const persistPipelineAfterGenerate = async () => {
  try {
    await flushPipelineSave()
  } catch (e) {
    console.error(e)
    ElMessage.warning('内容已写入本机，同步服务器失败，请检查网络或后端')
  }
}

const fullContentEditOpen = ref(false)
const fullContentEditDraft = ref('')
const fullContentEditMeta = ref({ si: -1, fi: -1, field: 'comic' })

const fullContentEditDialogTitle = computed(() => {
  const f = fullContentEditMeta.value.field
  if (f === 'shot') return '编辑画面主述'
  if (f === 'anim') return '编辑动画提示词'
  return '编辑漫画提示词'
})

const fullContentEditPlaceholder = computed(() => {
  const f = fullContentEditMeta.value.field
  if (f === 'shot') return '例如：【特写】夜灯在床头柜上投下暖黄色光晕…'
  if (f === 'anim') return '动画向：景别、运镜、节奏、光影等'
  return '漫画向：构图、格距、线稿与黑白关系等'
})

const openFullContentEdit = (si, fi, field) => {
  if (isCompletedNodeReadonly.value) return
  const n = currentNode.value
  const sh = n?.fullContentGen?.scenes?.[si]?.shots?.[fi]
  if (!sh) return
  fullContentEditMeta.value = { si, fi, field }
  if (field === 'shot') fullContentEditDraft.value = String(sh.shotText || '')
  else if (field === 'comic') fullContentEditDraft.value = String(sh.comicDesc || '')
  else fullContentEditDraft.value = String(sh.animDesc || '')
  fullContentEditOpen.value = true
}

const saveFullContentEdit = () => {
  if (isCompletedNodeReadonly.value) return
  const n = currentNode.value
  const { si, fi, field } = fullContentEditMeta.value
  const sh = n?.fullContentGen?.scenes?.[si]?.shots?.[fi]
  if (!sh) {
    fullContentEditOpen.value = false
    return
  }
  const v = String(fullContentEditDraft.value ?? '')
  if (field === 'shot') sh.shotText = v
  else if (field === 'comic') sh.comicDesc = v
  else sh.animDesc = v
  syncFullContentToOutput(n)
  persistState()
  fullContentEditOpen.value = false
  ElMessage.success('已保存')
}

const copyFullContentField = async (text) => {
  const t = String(text || '').trim()
  if (!t) {
    ElMessage.warning('内容为空')
    return
  }
  try {
    await navigator.clipboard.writeText(t)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

watch(
  () => (currentNode.value?.name === '完整内容生成' ? activeNodeIndex.value : null),
  () => {
    const n = currentNode.value
    if (n?.name === '完整内容生成') ensureFullContentGenState(n)
  },
  { immediate: true },
)

/** 与后端 POST …/pipeline-state/load|save 及本地缓存结构对齐（支持 snake_case / 历史 camelCase） */
const applyPipelinePayload = (parsed) => {
  if (!parsed || !Array.isArray(parsed.nodes) || !parsed.nodes.length) return false
  const ai = Number.isInteger(parsed.active_node_index)
    ? parsed.active_node_index
    : Number.isInteger(parsed.activeNodeIndex)
      ? parsed.activeNodeIndex
      : 0
  const mu = Number.isInteger(parsed.max_unlocked_index)
    ? parsed.max_unlocked_index
    : Number.isInteger(parsed.maxUnlockedIndex)
      ? parsed.maxUnlockedIndex
      : Math.max(ai, 0)
  nodes.value = parsed.nodes.map((node) => ({
    enabled: true,
    modelId: null,
    promptId: null,
    ...node,
    outputText: node.outputText ?? '',
    inputText: node.inputText ?? '',
    frameDecomposition: node.frameDecomposition,
    sceneDecomposition: node.sceneDecomposition,
    fullContentGen: node.fullContentGen,
  }))
  activeNodeIndex.value = ai
  maxUnlockedIndex.value = mu
  if (activeNodeIndex.value >= nodes.value.length) activeNodeIndex.value = 0
  if (maxUnlockedIndex.value >= nodes.value.length) maxUnlockedIndex.value = nodes.value.length - 1
  nextTick(() => {
    syncSceneReviewRevisedDraftFromOutput()
    syncFrameReviewOptimizedDraftFromOutput()
    const n = nodes.value[activeNodeIndex.value]
    if (n?.name === '完整内容生成') ensureFullContentGenState(n)
  })
  return true
}

let pipelineSaveTimer = null

const syncLocalStorageFromState = () => {
  localStorage.setItem(
    STORAGE_KEY.value,
    JSON.stringify({
      activeNodeIndex: activeNodeIndex.value,
      maxUnlockedIndex: maxUnlockedIndex.value,
      nodes: nodes.value,
    }),
  )
}

/** 仅写本地缓存（切换步骤查看时不应触发 pipeline-state/save） */
const persistViewportLocalOnly = () => {
  syncLocalStorageFromState()
}

const buildPipelinePayloadForApi = () => ({
  active_node_index: activeNodeIndex.value,
  max_unlocked_index: maxUnlockedIndex.value,
  nodes: JSON.parse(JSON.stringify(nodes.value)),
})

const savePipelineToServer = () =>
  http.post('/storyboards/pipeline-state/save', {
    storyboard_id: sceneId,
    ...buildPipelinePayloadForApi(),
  })

const flushPipelineSave = async () => {
  clearTimeout(pipelineSaveTimer)
  pipelineSaveTimer = null
  syncLocalStorageFromState()
  await savePipelineToServer()
}

const loadStateFromLocalStorage = () => {
  const raw = localStorage.getItem(STORAGE_KEY.value)
  if (!raw) {
    nodes.value = defaultNodes()
    activeNodeIndex.value = 0
    maxUnlockedIndex.value = 0
    nextTick(() => {
      syncSceneReviewRevisedDraftFromOutput()
      syncFrameReviewOptimizedDraftFromOutput()
    })
    return
  }
  try {
    const parsed = JSON.parse(raw)
    if (!applyPipelinePayload(parsed)) {
      nodes.value = defaultNodes()
      activeNodeIndex.value = 0
      maxUnlockedIndex.value = 0
      nextTick(() => {
        syncSceneReviewRevisedDraftFromOutput()
        syncFrameReviewOptimizedDraftFromOutput()
      })
    }
  } catch {
    nodes.value = defaultNodes()
    activeNodeIndex.value = 0
    maxUnlockedIndex.value = 0
    nextTick(() => {
      syncSceneReviewRevisedDraftFromOutput()
      syncFrameReviewOptimizedDraftFromOutput()
    })
  }
}

const canViewNodeDetail = (idx) => {
  const node = nodes.value[idx]
  if (!node || node.enabled === false) return false
  return idx <= maxUnlockedIndex.value
}

const isNodeUnlocked = (idx) => idx <= maxUnlockedIndex.value

const openNode = async (idx) => {
  if (!canViewNodeDetail(idx)) return
  activeNodeIndex.value = idx
  persistViewportLocalOnly()
  await fetchAiRunDiagnostics({ full: false })
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
    sceneDecomposition: i > idx ? undefined : node.sceneDecomposition,
    fullContentGen: i > idx ? undefined : node.fullContentGen,
  }))
  activeNodeIndex.value = idx
  if (idx > maxUnlockedIndex.value) maxUnlockedIndex.value = idx
  maxUnlockedIndex.value = idx
  persistState()
  ElMessage.success(`已重置到节点：${nodes.value[idx].name}`)
}

const resetToCurrentNode = () => resetToNode(activeNodeIndex.value)

const completeNode = async () => {
  if (!currentNode.value) return
  if (currentNode.value.completed) {
    ElMessage.warning('当前节点已完成，请先点击「重置到当前节点」后再编辑或保存并下一步')
    return
  }
  if (currentNode.value.name === '场景分解') {
    ensureSceneDecompositionState(currentNode.value)
    syncSceneDecompToOutput(currentNode.value)
  }
  if (currentNode.value.name === '画面分解') {
    ensureFrameDecompositionState(currentNode.value)
    syncFrameDecompToOutput(currentNode.value)
  }
  if (currentNode.value.name === '场景评审') {
    const srOk = applySceneReviewStructuredToOutput(currentNode.value, sceneReviewRevisedEditScenes.value)
    if (!srOk) {
      ElMessage.error('无法完成节点：场景评审输出 JSON 无效或无法写回「修改后」')
      return
    }
    sceneReviewRevising.value = false
    syncSceneReviewRevisedDraftFromOutput()
  }
  if (currentNode.value.name === '画面评审') {
    let ok = false
    if (frameReviewOptimizedEditScenes.value?.length) {
      ok = applyFrameReviewOptimizedStructuredToOutput(currentNode.value, frameReviewOptimizedEditScenes.value)
    }
    if (!ok) {
      ok = applyFrameReviewOptimizedDraftToOutput(currentNode.value, frameReviewOptimizedDraft.value)
    }
    if (!ok) {
      ElMessage.error('无法完成节点：画面评审输出 JSON 无效或无法写回「优化分镜」')
      return
    }
    frameReviewRevising.value = false
    syncFrameReviewOptimizedDraftFromOutput()
  }
  if (currentNode.value.name === '完整内容生成') {
    ensureFullContentGenState(currentNode.value)
    syncFullContentToOutput(currentNode.value)
  }
  if (!String(currentNode.value.outputText || '').trim()) {
    const tail =
      currentNode.value.name === '完整内容生成' ? '再点「完成」' : '再点「保存并下一步」'
    ElMessage.warning(`请先点击「生成」产生本节点输出内容后，${tail}`)
    return
  }
  currentNode.value.completed = true
  let next = activeNodeIndex.value + 1
  while (next < nodes.value.length && nodes.value[next].enabled === false) next += 1
  if (next < nodes.value.length) {
    activeNodeIndex.value = next
    if (next > maxUnlockedIndex.value) maxUnlockedIndex.value = next
  }
  persistState()
  const movedToNext = next < nodes.value.length
  try {
    await flushPipelineSave()
  } catch (e) {
    console.error(e)
    const d = e?.response?.data?.detail
    const msg =
      typeof d === 'string' ? d : '保存到服务器失败，进度已写在浏览器本地，请检查网络或后端后重试'
    ElMessage.error(msg)
    return
  }
  ElMessage.success('节点已完成')
  if (movedToNext) {
    await runCurrentPipelineNodeAiIfReady()
    try {
      const { data } = await http.post('/storyboards/pipeline-state/load', { storyboard_id: sceneId })
      if (data?.nodes?.length) {
        applyPipelinePayload(data)
        syncLocalStorageFromState()
      }
    } catch (e) {
      console.error(e)
    }
    await fetchAiRunDiagnostics({ full: false })
  }
}

const runCurrentNode = async () => {
  if (!currentNode.value) return
  if (isCompletedNodeReadonly.value) return
  if (!assertStoryboardLlmReady()) return
  if (!assertCurrentNodePromptConfigured()) return
  const customText = currentNode.value.inputText?.trim()
  let upstreamBlock = ''
  if (currentNode.value.name === '场景评审') {
    const up = getImmediateUpstreamOutput()
    if (up?.text?.trim()) {
      upstreamBlock = `【待评审内容（来自上游节点「${up.name}」）】\n${up.text}`
    } else if (!customText) {
      ElMessage.warning('未检测到上一节点输出：请先完成「场景分解」等上游步骤，或在自定义提示词中粘贴待评审全文。')
      return
    }
  }
  if (currentNode.value.name === '画面评审') {
    const up = getImmediateUpstreamOutput()
    if (up?.text?.trim()) {
      upstreamBlock = `【待评审分镜（来自上游节点「${up.name}」）】\n${up.text}`
    } else if (!customText) {
      ElMessage.warning('未检测到上一节点输出：请先完成「画面分解」等步骤，或在自定义提示词中粘贴待评审分镜 JSON。')
      return
    }
  }
  if (currentNode.value.name === '完整内容生成') {
    ensureFullContentGenState(currentNode.value)
    if (!currentNode.value.fullContentGen?.scenes?.length) {
      ElMessage.warning('暂无场景/画面：请先完成上游画面评审或画面分解后再生成')
      return
    }
    await runFullContentGenByScenes()
    return
  }
  let defaultText = [String(defaultPromptText.value || '').trim(), upstreamBlock].filter(Boolean).join('\n\n')
  submitLoading.value = true
  try {
    const themeCtx = 'full'
    const { data } = await http.post(
      resolveAiPostUrl(currentNode.value?.name),
      buildAiRunBody(defaultText, customText || '', currentNode.value.modelId ?? null, themeCtx),
      { timeout: 300000 },
    )
    const out = modelOutputRaw(data)
    currentNode.value.outputText = out
    if (currentNode.value.name === '场景评审') {
      sceneReviewRevising.value = false
      syncSceneReviewRevisedDraftFromOutput()
    }
    if (currentNode.value.name === '画面评审') {
      frameReviewRevising.value = false
      syncFrameReviewOptimizedDraftFromOutput()
    }
    await persistPipelineAfterGenerate()
    ElMessage.success('生成成功，已保存')
  } catch (e) {
    const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(String(e?.message || ''))
    if (isTimeout) {
      ElMessage.error('请求超时（大模型响应较慢）。若网络正常可稍后重试；仍失败可检查后端到模型服务的延迟。')
      return
    }
    const d = e?.response?.data?.detail
    const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg || x).join('; ') : '生成失败'
    ElMessage.error(msg)
  } finally {
    submitLoading.value = false
  }
}

/**
 * 仅在「保存并下一步」进入下一节点时按需拉 AI；切换步骤查看不自动请求模型。
 */
const runCurrentPipelineNodeAiIfReady = async () => {
  const n = currentNode.value
  if (!n || n.enabled === false) return
  if (n.completed) return
  if (String(n.outputText ?? '').trim()) return
  const name = n.name
  if (name === '故事描述') return
  if (name === '完整内容生成') return
  if (!assertStoryboardLlmReady({ silent: true })) return
  if (!assertCurrentNodePromptConfigured({ silent: true })) return
  const up = getImmediateUpstreamOutput()
  if (!up?.text?.trim()) return
  const autoSupported =
    name === '场景分解' || name === '场景评审' || name === '画面分解' || name === '画面评审'
  if (!autoSupported) return
  if (name === '场景分解') {
    await runSceneDecompositionAi()
  } else if (name === '画面分解') {
    await runFrameDecompositionAi()
  } else {
    await runCurrentNode()
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

const copyFrameReviewOptimizedPlain = async () => {
  const plain = frameReviewDiffRevisedPlain.value?.trim()
  if (!plain) {
    ElMessage.warning('「修改后」分镜正文为空，暂无可复制内容')
    return
  }
  try {
    await navigator.clipboard.writeText(plain)
    ElMessage.success('已复制修改后分镜（可读文本）')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const fetchScene = async () => {
  const { data } = await http.get('/storyboards')
  scene.value = data.find((item) => item.id === sceneId) || null
}

const buildAiRunBody = (defaultText, inputText, modelId, themeContextMode = 'full') => ({
  default_text: String(defaultText ?? ''),
  input_text: String(inputText ?? ''),
  theme_id: scene.value?.theme_id ?? null,
  storyboard_id: sceneId,
  model_id: modelId ?? null,
  theme_context_mode: themeContextMode,
})

/** 内置默认节点走独立 /ai/* 接口；自定义节点仍用 /run */
const STORYBOARD_AI_SUFFIX = {
  故事描述: 'story-description',
  场景分解: 'scene-decomposition',
  场景评审: 'scene-review',
  画面分解: 'frame-decomposition',
  画面评审: 'frame-review',
}

const storyboardAiEndpoint = (suffix) => `/storyboards/ai/${suffix}`

const resolveAiPostUrl = (nodeName, kind = null) => {
  if (kind === 'single-frame-description') return storyboardAiEndpoint('single-frame-description')
  if (kind === 'single-scene-decomposition') return storyboardAiEndpoint('single-scene-decomposition')
  if (kind === 'single-scene-card-decomposition') return storyboardAiEndpoint('single-scene-card-decomposition')
  const suf = nodeName ? STORYBOARD_AI_SUFFIX[nodeName] : null
  if (suf) return storyboardAiEndpoint(suf)
  return '/storyboards/run'
}

const modelOutputRaw = (data) => data?.raw_output ?? data?.output_text ?? ''

/**
 * 仅请求并合并一个场景（批量与单场景「重新生成」共用）。
 * @param {number} si 场景下标 0-based
 * @param {{ batchMode?: boolean, batchTotal?: number }} meta
 * @returns {Promise<boolean>}
 */
const executeFullContentGenOneScene = async (si, meta = {}) => {
  const node = currentNode.value
  if (!node || node.name !== '完整内容生成') return false
  const genScenes = node.fullContentGen?.scenes
  const batchTotal = meta.batchTotal ?? genScenes?.length ?? 0
  if (!genScenes?.[si]) return false
  const template = String(defaultPromptText.value || '').trim()
  if (!template) {
    if (!meta.batchMode) ElMessage.warning('请先在「自定义节点」为「完整内容生成」选择提示词模板')
    return false
  }
  const customText = node.inputText?.trim() || ''
  const ctx = buildFullContentBatchPromptContextForScene(si)
  const defaultText = [template, FULL_CONTENT_PER_SCENE_JSON_RULE, ctx].filter(Boolean).join('\n\n')
  const label = meta.batchMode ? `${si + 1}/${batchTotal}` : `${si + 1}`
  try {
    const { data } = await http.post(
      resolveAiPostUrl(node.name),
      buildAiRunBody(defaultText, customText, node.modelId ?? null, 'appearance_only'),
      { timeout: 300000 },
    )
    const out = modelOutputRaw(data)
    const blob = extractJsonObjectString(String(out || ''))
    if (!blob) {
      ElMessage.warning(
        meta.batchMode
          ? `场景 ${label}：未找到完整 JSON 对象（可能被截断），已跳过；其它场景不受影响`
          : `场景 ${label}：未找到完整 JSON 对象，未更新`,
      )
      return false
    }
    let parsed
    try {
      parsed = JSON.parse(blob)
    } catch {
      ElMessage.warning(meta.batchMode ? `场景 ${label}：JSON 解析失败，已跳过` : `场景 ${label}：JSON 解析失败，未更新`)
      return false
    }
    const merged = mergeFullContentOneSceneFromParsed(node, si, parsed)
    if (!merged.ok) {
      ElMessage.warning(
        meta.batchMode ? `场景 ${label}：${merged.detail || '合并失败'}` : `场景 ${label}：${merged.detail || '合并失败'}`,
      )
      return false
    }
    syncFullContentToOutput(node)
    await persistPipelineAfterGenerate()
    if (!meta.batchMode) ElMessage.success(`场景 ${si + 1} 已重新生成并保存`)
    return true
  } catch (e) {
    const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(String(e?.message || ''))
    if (isTimeout) {
      ElMessage.error(meta.batchMode ? `场景 ${label}：请求超时，已跳过该场景` : `场景 ${label}：请求超时`)
    } else {
      const d = e?.response?.data?.detail
      const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg || x).join('; ') : '请求失败'
      ElMessage.error(meta.batchMode ? `场景 ${label}：${msg}` : `场景 ${label}：${msg}`)
    }
    return false
  }
}

/** 完整内容：按场景逐个请求，每场景成功后立即写回 outputText 并 pipeline save */
const runFullContentGenByScenes = async () => {
  const node = currentNode.value
  if (!node || node.name !== '完整内容生成') return
  const genScenes = node.fullContentGen?.scenes
  if (!genScenes?.length) return
  const template = String(defaultPromptText.value || '').trim()
  if (!template) {
    ElMessage.warning('请先在「自定义节点」为「完整内容生成」选择提示词模板')
    return
  }
  fullContentBatchRunning.value = true
  let ok = 0
  let fail = 0
  try {
    const n = genScenes.length
    for (let si = 0; si < n; si++) {
      fullContentSceneLoadingSi.value = si
      try {
        const success = await executeFullContentGenOneScene(si, { batchMode: true, batchTotal: n })
        if (success) ok += 1
        else fail += 1
      } finally {
        fullContentSceneLoadingSi.value = -1
      }
    }
    if (fail === 0) ElMessage.success(`完整内容已全部生成并保存（共 ${ok} 个场景）`)
    else if (ok > 0) ElMessage.warning(`完整内容：成功 ${ok} 个场景，失败或跳过 ${fail} 个；已成功部分已保存。`)
    else ElMessage.error('完整内容：全部场景均未成功，请检查网络与提示词后重试')
  } finally {
    fullContentBatchRunning.value = false
    fullContentSceneLoadingSi.value = -1
  }
}

/** 单场景重新生成（不影响其它场景已写入的数据） */
const regenerateFullContentScene = async (si) => {
  if (!currentNode.value || currentNode.value.name !== '完整内容生成') return
  if (fullContentBatchRunning.value) {
    ElMessage.warning('正在按顺序生成全部场景，请结束后再单独重试')
    return
  }
  if (fullContentSceneLoadingSi.value !== -1) {
    ElMessage.warning('另有场景正在请求中，请稍候')
    return
  }
  if (!assertStoryboardLlmReady()) return
  if (!assertCurrentNodePromptConfigured()) return
  ensureFullContentGenState(currentNode.value)
  if (!currentNode.value.fullContentGen?.scenes?.[si]) return
  fullContentSceneLoadingSi.value = si
  try {
    await executeFullContentGenOneScene(si, { batchMode: false })
  } finally {
    fullContentSceneLoadingSi.value = -1
  }
}

/**
 * @param {{ full?: boolean }} options full=true 时拉摘要+场景树+当前节点（调试区）；默认仅 pipeline-node 详情
 */
const fetchAiRunDiagnostics = async (options = {}) => {
  const full = options.full === true
  try {
    if (full) {
      const [sumRes, treeRes] = await Promise.all([
        http.post('/storyboards/ai-run/summary', { storyboard_id: sceneId }),
        http.post('/storyboards/ai-run/scene-frame-tree', { storyboard_id: sceneId }),
      ])
      const pack = {
        summary: sumRes.data,
        scene_tree: treeRes.data,
        pipeline_node: null,
      }
      const nid = currentNode.value?.id
      if (nid) {
        try {
          const nodeRes = await http.post('/storyboards/ai-run/pipeline-node', {
            storyboard_id: sceneId,
            node_id: nid,
          })
          pack.pipeline_node = nodeRes.data
        } catch {
          pack.pipeline_node = {
            _note: '服务端流水线中未找到该 node_id，请先「保存」同步 pipeline-state',
            node_id: nid,
          }
        }
      }
      aiRunDiagnostics.value = pack
      return
    }
    const nid = currentNode.value?.id
    if (!nid) return
    try {
      const nodeRes = await http.post('/storyboards/ai-run/pipeline-node', {
        storyboard_id: sceneId,
        node_id: nid,
      })
      const prev = aiRunDiagnostics.value || {}
      aiRunDiagnostics.value = { ...prev, pipeline_node: nodeRes.data }
    } catch {
      const prev = aiRunDiagnostics.value || {}
      aiRunDiagnostics.value = {
        ...prev,
        pipeline_node: {
          _note: '服务端流水线中未找到该 node_id，请先「保存」同步 pipeline-state',
          node_id: nid,
        },
      }
    }
  } catch {
    if (full) aiRunDiagnostics.value = null
  }
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
      sceneDecomposition: prev?.sceneDecomposition ?? n.sceneDecomposition,
      fullContentGen: prev?.fullContentGen ?? n.fullContentGen,
      fullContentAiModifyText: prev?.fullContentAiModifyText ?? n.fullContentAiModifyText ?? '',
      fullContentAiTarget: prev?.fullContentAiTarget ?? n.fullContentAiTarget ?? null,
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
  let loadedFromServer = false
  try {
    const { data } = await http.post('/storyboards/pipeline-state/load', { storyboard_id: sceneId })
    if (data?.nodes?.length) {
      applyPipelinePayload(data)
      syncLocalStorageFromState()
      loadedFromServer = true
    }
  } catch {
    /* 离线或接口不可用时退回本地 */
  }
  if (!loadedFromServer) {
    loadStateFromLocalStorage()
  }
  if (maxUnlockedIndex.value < activeNodeIndex.value) maxUnlockedIndex.value = activeNodeIndex.value
  await fetchNodeOptions()
  await fetchScene()
  await fetchAiRunDiagnostics({ full: false })
  await nextTick()
  if (!loadedFromServer && nodes.value.length) {
    try {
      await flushPipelineSave()
    } catch {
      /* 首次把本地草稿推上服务器失败时，仍可由后续 persistState 重试 */
    }
  }
})
</script>

<style scoped>
.run-ctx-collapse {
  margin-bottom: 12px;
}

.run-ctx-pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  max-height: 360px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.node-readonly-banner {
  margin-bottom: 12px;
}

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

.review-block-spacing {
  margin-bottom: 12px;
}

.review-revised-editor-input {
  width: 100%;
}

.review-revised-editor-input :deep(.el-textarea__inner) {
  font-family: system-ui, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  line-height: 1.65;
  color: #303133;
  min-height: 280px !important;
}

.fr-opt-empty {
  padding: 16px;
  color: #909399;
  font-size: 13px;
  line-height: 1.6;
  background: #fafafa;
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  margin-bottom: 12px;
}

.fr-opt-modules {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 12px;
  max-height: min(52vh, 520px);
  overflow-y: auto;
  padding-right: 4px;
}

.review-compare--frame-editing .fr-opt-modules {
  max-height: none;
  overflow-y: visible;
}

.fr-opt-frame-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.fr-opt-scene-card {
  border: 1px solid #dcdfe6;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.fr-opt-scene-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 10px 12px;
  background: linear-gradient(180deg, #ecf5ff 0%, #f5f7fa 100%);
  border-bottom: 1px solid #ebeef5;
}

.fr-opt-scene-badge {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  color: #409eff;
}

.fr-opt-scene-title-input {
  flex: 1;
  min-width: 160px;
}

.fr-opt-frames {
  padding: 10px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fr-opt-frame-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.fr-opt-frame-label {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
}

.fr-opt-frame-textarea {
  width: 100%;
}

.fr-opt-frame-textarea :deep(.el-textarea__inner) {
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
}

.story-out-body {
  white-space: pre-wrap;
  word-break: break-word;
  min-height: 90px;
  max-height: min(42vh, 360px);
  overflow-y: auto;
  scrollbar-gutter: stable;
  padding: 14px 16px;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.65;
  color: #303133;
}

.fr-review-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.fr-review-block {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 12px 14px;
  background: #fafafa;
}

.fr-review-block-title {
  font-weight: 700;
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}

.fr-review-block-body {
  font-size: 14px;
  line-height: 1.65;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}

.fr-review-summary {
  background: linear-gradient(180deg, #f0f9ff 0%, #fafafa 100%);
  border-radius: 6px;
  padding: 10px 12px;
}

.fr-review-list {
  margin: 0;
  padding-left: 1.25rem;
  color: #303133;
  line-height: 1.6;
  font-size: 14px;
}

.fr-review-scene {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 12px 14px;
  background: #fff;
}

.fr-review-scene-title {
  font-weight: 700;
  font-size: 14px;
  color: #409eff;
  margin-bottom: 10px;
}

.fr-review-frames {
  margin: 0;
  padding-left: 1.25rem;
  color: #303133;
  font-size: 14px;
  line-height: 1.55;
}

.fr-review-frame-item {
  margin-bottom: 8px;
}

.fr-review-frame-label {
  font-weight: 600;
  color: #606266;
  margin-right: 8px;
}

.fr-review-frame-desc {
  white-space: pre-wrap;
  word-break: break-word;
}

.fr-review-frame-empty {
  font-size: 13px;
  color: #909399;
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

.review-issue-checklist {
  margin-top: 12px;
}

.review-issue-checklist-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.review-issue-pair-list {
  margin: 0;
  padding-left: 0;
  list-style: none;
  color: #606266;
  line-height: 1.65;
}

.review-issue-pair-item {
  margin-bottom: 10px;
}

.review-issue-pair-item:last-child {
  margin-bottom: 0;
}

.review-issue-line {
  white-space: pre-wrap;
  word-break: break-word;
}

.review-issue-line--sub {
  margin-top: 4px;
  padding-left: 0.5rem;
  color: #409eff;
}

.fr-tag {
  display: inline-block;
  margin-right: 8px;
  padding: 0 7px;
  font-size: 11px;
  font-weight: 600;
  color: #1a5fb4;
  background: rgba(64, 158, 255, 0.12);
  border-radius: 4px;
  vertical-align: text-bottom;
}

.review-diff-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px 20px;
  margin-bottom: 10px;
  font-size: 12px;
  color: #606266;
}

.review-diff-legend > span {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.review-diff-legend-note {
  flex-basis: 100%;
  font-size: 11px;
  color: #909399;
  padding-left: 2px;
}

.review-diff-legend-swatch {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 6px;
  flex-shrink: 0;
}

.review-diff-legend-swatch.review-diff-eq {
  background: #303133;
}

.review-diff-legend-swatch.review-diff-before {
  background: rgba(248, 113, 113, 0.45);
  border: 1px solid rgba(239, 68, 68, 0.35);
}

.review-diff-legend-swatch.review-diff-after {
  background: rgba(74, 222, 128, 0.45);
  border: 1px solid rgba(34, 197, 94, 0.35);
}

.review-diff-base-tag {
  margin-top: 4px;
  font-size: 11px;
  font-weight: 500;
  color: #909399;
  line-height: 1.35;
}

.review-pane-body--diff {
  font-family: system-ui, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  /* 在 flex 列中必须可收缩，否则内容撑满、不出现滚动条，联动滚动也不会触发 */
  flex: 1 1 0;
  min-height: 0;
  overflow-y: scroll;
  overflow-x: hidden;
  scrollbar-gutter: stable;
  overscroll-behavior: contain;
}

.review-diff-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.65;
  color: #303133;
}

.review-diff-eq {
  color: #303133;
}

.review-diff-before {
  background: rgba(254, 226, 226, 0.95);
  color: #303133;
  border-radius: 4px;
  box-shadow: inset 0 0 0 1px rgba(248, 113, 113, 0.35);
}

.review-diff-after {
  background: rgba(220, 252, 231, 0.95);
  color: #303133;
  border-radius: 4px;
  box-shadow: inset 0 0 0 1px rgba(74, 222, 128, 0.4);
}

.review-diff-empty {
  margin: 0;
  color: #909399;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-word;
}

.review-compare {
  display: flex;
  gap: 12px;
  align-items: stretch;
  min-height: min(320px, 50vh);
  max-height: min(520px, 72vh);
}

.review-compare.review-compare--frame-editing {
  max-height: min(88vh, 920px);
  min-height: min(380px, 58vh);
}

.sr-scene-toolbar {
  margin-bottom: 10px;
  padding: 8px 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fafafa;
}

.sr-per-scene-block {
  margin-bottom: 16px;
}

.output-card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.sr-row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.sr-inline-after-input :deep(textarea) {
  font-family: inherit;
  line-height: 1.55;
}

.sr-per-scene-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 8px;
  color: #303133;
}

.sr-per-scene-compare {
  min-height: 120px;
  max-height: min(360px, 55vh);
}

.sr-edit-scene-card {
  margin-bottom: 14px;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fafafa;
}

.sr-edit-scene-label {
  font-weight: 600;
  font-size: 12px;
  margin-bottom: 8px;
  color: #606266;
}

.sr-edit-title {
  margin-bottom: 8px;
}

.review-pane {
  flex: 1;
  min-width: 0;
  min-height: 0;
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
  align-items: flex-start;
  text-align: left;
  gap: 10px;
}

.review-pane-sub {
  margin-top: 4px;
  font-size: 11px;
  font-weight: 500;
  color: #909399;
  line-height: 1.35;
}

.review-pane-actions {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.review-pane-body--edit-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

/* 编辑分块时避免 420px 顶死导致文本域难以操作 */
.review-pane-body.review-pane-body--diff.review-pane-body--edit-stack {
  max-height: min(78vh, 800px);
}

.review-session-diff-wrap {
  flex-shrink: 0;
  padding-top: 4px;
  border-top: 1px dashed #e4e7ed;
  max-height: min(200px, 28vh);
  overflow-y: auto;
}

.review-session-diff-title {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 8px;
}

.review-session-diff-block + .review-session-diff-block {
  margin-top: 10px;
}

.review-session-diff-subtitle {
  font-size: 11px;
  color: #909399;
  margin-bottom: 4px;
}

.review-pane-body {
  flex: 1 1 0;
  min-height: 0;
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

/* 场景分解（卡片模式，与画面分解布局一致） */
.sd-panel {
  margin-bottom: 12px;
}

.sd-ai-block {
  margin-bottom: 20px;
}

.sd-ai-label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.sd-ai-inner {
  position: relative;
}

.sd-ai-inner--slash {
  position: relative;
}

.sd-ai-composer-shell {
  position: relative;
  border: 1px solid var(--el-border-color);
  border-radius: var(--el-border-radius-base);
  background: var(--el-fill-color-blank);
  padding: 8px 11px 10px;
  transition:
    border-color 0.2s cubic-bezier(0.645, 0.045, 0.355, 1),
    box-shadow 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
}

.sd-ai-composer-shell:focus-within:not(.sd-ai-composer-shell--disabled) {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary) inset;
}

.sd-ai-composer-shell--disabled {
  cursor: not-allowed;
  background: var(--el-fill-color-light);
  box-shadow: none;
}

.sd-scope-chip-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}

.sd-scope-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 4px 10px;
  border-radius: 6px;
  background: linear-gradient(180deg, #e8f3ff 0%, #d0e8ff 100%);
  border: 1px solid #8cc4ff;
  color: #1565c0;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.35;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65);
}

.sd-scope-chip-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  max-width: min(100%, 520px);
}

.sd-scope-chip-x {
  flex-shrink: 0;
  margin: 0;
  padding: 0 4px;
  border: none;
  background: transparent;
  color: #1976d2;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  border-radius: 4px;
}

.sd-scope-chip-x:hover {
  background: rgba(25, 118, 210, 0.12);
}

.sd-ai-textarea-wrap {
  position: relative;
  width: 100%;
}

.sd-ai-input-inside {
  width: 100%;
}

.sd-ai-input-inside :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  background: transparent;
  padding: 4px 0 0;
  min-height: 120px;
}

.sd-ai-input-inside :deep(.el-textarea__inner:hover),
.sd-ai-input-inside :deep(.el-textarea__inner:focus) {
  box-shadow: none;
}

.sd-ai-input-inside :deep(.el-textarea) {
  box-shadow: none;
}

.sd-ai-input-inside :deep(.el-textarea.is-disabled .el-textarea__inner) {
  background: transparent;
  box-shadow: none;
}

.sd-slash-menu {
  position: absolute;
  z-index: 30;
  margin-top: 0;
  max-height: 240px;
  overflow-y: auto;
  background: var(--el-bg-color-overlay, #fff);
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 6px;
  box-shadow: var(--el-box-shadow-light, 0 4px 12px rgba(0, 0, 0, 0.12));
}

.sd-slash-item {
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  line-height: 1.4;
}

.sd-slash-item:hover,
.sd-slash-item.is-active {
  background: #ecf5ff;
  color: #409eff;
}

.sd-slash-empty {
  padding: 10px 12px;
  color: #909399;
  font-size: 13px;
}

.sd-ai-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.sd-empty {
  padding: 24px;
  text-align: center;
  color: #909399;
  font-size: 14px;
  line-height: 1.6;
}

.sd-empty p {
  margin: 0 0 12px;
}

.sd-scene-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sd-scene-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  padding: 0;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.sd-scene-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: linear-gradient(180deg, #f6ffed 0%, #f9fafb 100%);
  border-bottom: 1px solid #ebeef5;
}

.sd-scene-head--edit {
  align-items: flex-start;
  gap: 10px;
}

.sd-scene-edit-fields {
  flex: 1;
  min-width: 0;
}

.sd-scene-title-input {
  width: 100%;
}

.sd-scene-edit-body {
  padding: 12px 16px 4px;
}

.sd-scene-title {
  font-size: 15px;
  font-weight: 600;
  color: #67c23a;
}

.sd-scene-body {
  margin: 0 16px;
  padding: 14px 0 4px;
  font-size: 14px;
  color: #303133;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.sd-scene-footer {
  margin: 0 16px 14px;
  padding-top: 10px;
  border-top: 1px dashed #dcdfe6;
}

.sd-scene-time {
  font-size: 12px;
  color: #909399;
}

/* 画面分解 */
.fd-panel {
  margin-bottom: 12px;
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

.fd-ai-inner--slash {
  position: relative;
}

/* 范围标签 + 多行输入：同一外框，视觉上「都在输入框里」 */
.fd-ai-composer-shell {
  position: relative;
  border: 1px solid var(--el-border-color);
  border-radius: var(--el-border-radius-base);
  background: var(--el-fill-color-blank);
  padding: 8px 11px 10px;
  transition:
    border-color 0.2s cubic-bezier(0.645, 0.045, 0.355, 1),
    box-shadow 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
}

.fd-ai-composer-shell:focus-within:not(.fd-ai-composer-shell--disabled) {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary) inset;
}

.fd-ai-composer-shell--disabled {
  cursor: not-allowed;
  background: var(--el-fill-color-light);
  box-shadow: none;
}

.fd-scope-chip-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}

.fd-scope-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 4px 10px;
  border-radius: 6px;
  background: linear-gradient(180deg, #e8f3ff 0%, #d0e8ff 100%);
  border: 1px solid #8cc4ff;
  color: #1565c0;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.35;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65);
}

.fd-scope-chip-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  max-width: min(100%, 520px);
}

.fd-scope-chip-x {
  flex-shrink: 0;
  margin: 0;
  padding: 0 4px;
  border: none;
  background: transparent;
  color: #1976d2;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  border-radius: 4px;
}

.fd-scope-chip-x:hover {
  background: rgba(25, 118, 210, 0.12);
}

.fd-ai-textarea-wrap {
  position: relative;
  width: 100%;
}

.fd-ai-input-inside {
  width: 100%;
}

.fd-ai-input-inside :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  background: transparent;
  padding: 4px 0 0;
  min-height: 120px;
}

.fd-ai-input-inside :deep(.el-textarea__inner:hover),
.fd-ai-input-inside :deep(.el-textarea__inner:focus) {
  box-shadow: none;
}

.fd-ai-input-inside :deep(.el-textarea) {
  box-shadow: none;
}

.fd-ai-input-inside :deep(.el-textarea.is-disabled .el-textarea__inner) {
  background: transparent;
  box-shadow: none;
}

.fd-slash-menu {
  position: absolute;
  z-index: 30;
  margin-top: 0;
  max-height: 240px;
  overflow-y: auto;
  background: var(--el-bg-color-overlay, #fff);
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 6px;
  box-shadow: var(--el-box-shadow-light, 0 4px 12px rgba(0, 0, 0, 0.12));
}

.fd-slash-item {
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  line-height: 1.4;
}

.fd-slash-item:hover,
.fd-slash-item.is-active {
  background: #ecf5ff;
  color: #409eff;
}

.fd-slash-empty {
  padding: 10px 12px;
  color: #909399;
  font-size: 13px;
}

.fd-ai-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
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
  gap: 12px;
  padding: 12px 16px;
  background: #f9fafb;
  border-bottom: 1px solid #ebeef5;
}

.fd-scene-head--edit {
  align-items: center;
}

.fd-scene-title {
  font-size: 15px;
  font-weight: 600;
  color: #409eff;
}

.fd-scene-desc-block {
  margin: 0 16px 12px;
  padding: 12px 14px;
  border-radius: 8px;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
}

.fd-scene-desc-label {
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 8px;
}

.fd-scene-desc-body {
  font-size: 14px;
  line-height: 1.65;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}

.fd-frames {
  padding: 8px 16px 4px;
  font-size: 14px;
  color: #303133;
  line-height: 1.65;
}

.fd-frames--edit {
  padding-bottom: 12px;
}

.fd-frame-edit-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.fd-frame-edit-row .fd-frame-label {
  flex-shrink: 0;
}

.fd-add-frame-btn {
  margin-top: 4px;
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

/* 完整内容生成 */
.fcg-input-hint {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.65;
  color: #606266;
}

.fcg-copy-spec-btn {
  margin-bottom: 10px;
}

.fcg-toolbar-card {
  margin-bottom: 12px;
}

.fcg-toolbar-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.fcg-toolbar-card--minimal .fcg-toolbar-row {
  justify-content: flex-end;
}

.fcg-format-collapse {
  margin-bottom: 14px;
}

.fcg-format-collapse :deep(.el-collapse-item__header) {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
}

.fcg-format-hint {
  font-size: 13px;
  line-height: 1.65;
  color: #606266;
}

.fcg-format-ul {
  margin: 0;
  padding-left: 1.25em;
  font-size: 13px;
  line-height: 1.65;
  color: #606266;
}

.fcg-format-ul li + li {
  margin-top: 6px;
}

.fcg-format-p {
  margin: 0 0 10px;
}

.fcg-format-p code {
  font-size: 12px;
  padding: 1px 4px;
  border-radius: 4px;
  background: #f0f2f5;
}

.fcg-format-note {
  font-size: 12px;
  color: #909399;
}

.fcg-format-pre {
  margin: 0 0 12px;
  padding: 12px 14px;
  background: #f5f7fa;
  color: #303133;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
}

.fcg-main-card {
  margin-bottom: 12px;
}

.fcg-main-card--pending .fcg-pending {
  padding: 40px;
  text-align: center;
  color: #909399;
  font-size: 14px;
}

.fcg-hero {
  padding-bottom: 16px;
  margin-bottom: 20px;
  border-bottom: 1px solid #ebeef5;
}

.fcg-hero-row {
  display: flex;
  gap: 12px;
  margin-bottom: 10px;
  align-items: baseline;
}

.fcg-hero-label {
  flex-shrink: 0;
  width: 88px;
  font-size: 13px;
  font-weight: 600;
  color: #909399;
}

.fcg-hero-value {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.fcg-story-block {
  margin-top: 14px;
}

.fcg-block-title {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 8px;
}

.fcg-story-body {
  font-size: 14px;
  line-height: 1.7;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: min(36vh, 300px);
  overflow-y: auto;
  scrollbar-gutter: stable;
  padding: 14px 16px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #ebeef5;
}

.fcg-empty {
  padding: 24px;
  text-align: center;
  color: #909399;
  font-size: 14px;
}

.fcg-scene-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.fcg-scene-card {
  border: 1px solid #dcdfe6;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.fcg-scene-card--loading-host {
  position: relative;
  min-height: 160px;
}

.fcg-scene-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 16px;
  background: linear-gradient(180deg, #ecf5ff 0%, #f5f9ff 100%);
  border-bottom: 1px solid #e4e7ed;
}

.fcg-scene-title {
  flex: 1;
  min-width: 0;
  font-size: 16px;
  font-weight: 700;
  color: #409eff;
}

.fcg-scene-regen-btn {
  flex-shrink: 0;
}

.fcg-scene-desc {
  padding: 12px 16px 8px;
  border-bottom: 1px dashed #ebeef5;
}

.fcg-inline-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 6px;
}

.fcg-scene-desc-body {
  font-size: 14px;
  line-height: 1.65;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 同一场景下多幅画面：共用一个外框，避免每幅像独立场景 */
.fcg-scene-shots {
  margin: 0 12px 14px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.fcg-scene-shots-label {
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  background: linear-gradient(180deg, #f4f6f9 0%, #eef1f6 100%);
  border-bottom: 1px solid #e4e7ed;
}

.fcg-shot-card {
  margin: 0;
  padding: 14px 16px;
  border-bottom: 1px solid #ebeef5;
  border-left: none;
  border-radius: 0;
  background: #fff;
}

.fcg-shot-card:last-child {
  border-bottom: none;
}

/* 「· 画面N：」主述行，对齐你提供的可读层级 */
.fcg-shot-lead {
  display: grid;
  grid-template-columns: auto auto 1fr auto;
  gap: 6px 10px;
  align-items: start;
  margin-bottom: 12px;
  font-size: 14px;
  line-height: 1.65;
  color: #303133;
}

@media (max-width: 700px) {
  .fcg-shot-lead {
    grid-template-columns: auto 1fr;
    grid-template-rows: auto auto;
  }

  .fcg-shot-bullet {
    grid-column: 1;
  }

  .fcg-shot-line-label {
    grid-column: 2;
  }

  .fcg-shot-line-body {
    grid-column: 1 / -1;
  }

  .fcg-shot-lead-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
}

.fcg-shot-bullet {
  color: #606266;
  font-weight: 700;
  user-select: none;
}

.fcg-shot-line-label {
  flex-shrink: 0;
  font-weight: 700;
  color: #606266;
  white-space: nowrap;
}

.fcg-shot-line-body {
  white-space: pre-wrap;
  word-break: break-word;
  min-width: 0;
}

.fcg-shot-lead-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  justify-content: flex-end;
  align-self: start;
}

.fcg-shot-prompts-label {
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 8px;
}

.fcg-shot-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 900px) {
  .fcg-shot-cols {
    grid-template-columns: 1fr;
  }
}

.fcg-shot-col {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px 12px;
  background: #fcfcfc;
}

.fcg-shot-col-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.fcg-shot-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  justify-content: flex-end;
}

.fcg-shot-text {
  font-size: 13px;
  line-height: 1.65;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
  min-height: 48px;
}
</style>
