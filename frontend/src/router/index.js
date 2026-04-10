import { createRouter, createWebHistory } from 'vue-router'
import StoryboardView from '../views/StoryboardView.vue'
import StoryboardRunView from '../views/StoryboardRunView.vue'
import LLMView from '../views/LLMView.vue'
import PromptView from '../views/PromptView.vue'
import ThemeView from '../views/ThemeView.vue'

const routes = [
  { path: '/', redirect: '/storyboards' },
  { path: '/themes', component: ThemeView },
  { path: '/storyboards', component: StoryboardView },
  { path: '/storyboards/:id/run', component: StoryboardRunView },
  { path: '/llm', component: LLMView },
  { path: '/prompts', component: PromptView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
