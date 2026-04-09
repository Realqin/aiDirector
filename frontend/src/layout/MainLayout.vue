<template>
  <el-container style="height: 100vh">
    <el-aside width="180px" style="background: #17233a; color: #fff">
      <div style="padding: 16px; font-size: 18px; font-weight: 700">AI 导演工作台</div>
      <el-menu :default-active="$route.path" router background-color="#17233a" text-color="#fff" active-text-color="#409EFF">
        <el-menu-item index="/storyboards">AI 分镜</el-menu-item>
        <el-menu-item index="/llm">LLM 配置</el-menu-item>
        <el-menu-item index="/prompts">提示词模板</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display:flex;align-items:center;font-size:22px;font-weight:600">{{ title }}</el-header>
      <el-main style="background:#f5f7fa">
        <el-card v-if="debugEncoding" style="margin-bottom: 12px" shadow="never">
          <template #header>
            <div style="font-weight: 600">编码诊断面板（临时）</div>
          </template>
          <div style="font-size: 13px; line-height: 1.8; word-break: break-all">
            <div><strong>title:</strong> {{ diagnose.title }}</div>
            <div><strong>title(unicode):</strong> {{ toUnicodeEscape(diagnose.title) }}</div>
            <div><strong>storyboard.name:</strong> {{ diagnose.storyboardName }}</div>
            <div><strong>storyboard.name(unicode):</strong> {{ toUnicodeEscape(diagnose.storyboardName) }}</div>
            <div><strong>prompt.name:</strong> {{ diagnose.promptName }}</div>
            <div><strong>prompt.name(unicode):</strong> {{ toUnicodeEscape(diagnose.promptName) }}</div>
          </div>
        </el-card>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'
import { useRoute } from 'vue-router'
import http from '../api/http'

const route = useRoute()

const title = computed(() => {
  if (route.path === '/llm') return 'LLM 配置'
  if (route.path === '/prompts') return '提示词模板'
  return 'AI 分镜'
})

const debugEncoding = computed(() => String(route.query.debugEncoding || '') === '1')
const diagnose = reactive({
  title: '',
  storyboardName: '',
  promptName: '',
})

const toUnicodeEscape = (value) => {
  if (!value) return ''
  return [...value]
    .map((ch) => `\\u${ch.charCodeAt(0).toString(16).padStart(4, '0')}`)
    .join('')
}

const loadDiagnostics = async () => {
  if (!debugEncoding.value) return
  diagnose.title = document.title || ''
  const [storyboardsRes, promptsRes] = await Promise.all([
    http.get('/storyboards'),
    http.get('/prompts'),
  ])
  diagnose.storyboardName = storyboardsRes.data?.[0]?.name || ''
  diagnose.promptName = promptsRes.data?.[0]?.name || ''
}

onMounted(loadDiagnostics)
</script>
