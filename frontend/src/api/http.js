import axios from 'axios'

/** 默认超时；大模型类接口请在请求上单独增大 timeout，避免 DevTools 显示 canceled。 */
const http = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  timeout: 60000,
})

export default http
