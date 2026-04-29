import axios from 'axios'
import { supabase } from '../lib/supabase'

const api = axios.create({
  baseURL: '/api',
  timeout: 0, // unlimited — 5GB uploads on slow connections can take 30+ minutes
  withCredentials: false,
  // Allow huge multipart bodies (axios default is 10MB)
  maxBodyLength: Infinity,
  maxContentLength: Infinity,
})

// Auth + debug interceptor — attaches the current Supabase JWT
api.interceptors.request.use(
  async (config) => {
    try {
      const { data } = await supabase.auth.getSession()
      const token = data?.session?.access_token
      if (token) {
        config.headers = config.headers || {}
        config.headers.Authorization = `Bearer ${token}`
      }
    } catch (e) {
      console.warn('[API] could not attach auth token:', e)
    }
    console.log('[API] Request:', config.method?.toUpperCase(), config.url, config.baseURL)
    return config
  },
  (error) => {
    console.error('[API] Request error:', error)
    return Promise.reject(error)
  }
)

// Add response interceptor for debugging
api.interceptors.response.use(
  (response) => {
    console.log('[API] Response:', response.status, response.config.url)
    return response
  },
  (error) => {
    console.error('[API] Response error:', error.message, error.code, error.config?.url)
    return Promise.reject(error)
  }
)

export const uploadVideo = (
  file,
  whisperModel,
  aiModel,
  onProgress,
  { mode = 'clips', numClips = 5, whisperLanguage = 'auto' } = {}
) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('whisper_model', whisperModel || 'base')
  formData.append('whisper_language', whisperLanguage || 'auto')
  formData.append('ai_model', aiModel || 'qwen3.5:32b-cloud')
  formData.append('mode', mode)
  formData.append('num_clips', String(numClips))
  // Don't set Content-Type header manually - axios/browser will set it with boundary
  return api.post('/upload', formData, {
    onUploadProgress: onProgress ? (progressEvent) => {
      const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
      onProgress(percentCompleted)
    } : undefined
  })
}

export const importYouTube = (
  url,
  whisperModel,
  aiModel,
  { mode = 'clips', numClips = 5, whisperLanguage = 'auto' } = {}
) => api.post('/import-youtube', {
  url,
  whisper_model: whisperModel || 'base',
  whisper_language: whisperLanguage || 'auto',
  ai_model: aiModel || 'qwen3.5:32b-cloud',
  mode,
  num_clips: numClips,
})

export const burnSubtitles = (clipId, opts = {}) => api.post(`/clips/${clipId}/burn-subtitles`, opts, { responseType: 'blob', timeout: 300000 })

export const streamCleanedVideo = (jobId) => `/api/jobs/${jobId}/cleaned/stream`
export const downloadCleanedVideo = (jobId) => `/api/jobs/${jobId}/cleaned/download`

export const getJob = (jobId) => api.get(`/jobs/${jobId}`)

export const getJobClips = (jobId) => api.get(`/jobs/${jobId}/clips`)

export const deleteJob = (jobId) => api.delete(`/jobs/${jobId}`)

export const resumeJob  = (jobId) => api.post(`/jobs/${jobId}/resume`)
export const restartJob = (jobId) => api.post(`/jobs/${jobId}/restart`)
export const retryJob   = resumeJob  // backwards-compat alias

export const cancelJob = (jobId) => api.post(`/jobs/${jobId}/cancel`)

export const downloadClip = (clipId) => `/api/clips/${clipId}/download`

export const streamClip = (clipId) => `/api/clips/${clipId}/stream`

export default api
