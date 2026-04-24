import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000, // 5 minutes for large uploads
})

export const uploadVideo = (
  file,
  whisperModel,
  aiModel,
  onProgress,
  { mode = 'clips', numClips = 5 } = {}
) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('whisper_model', whisperModel || 'base')
  formData.append('ai_model', aiModel || 'gemma4:31b-cloud')
  formData.append('mode', mode)
  formData.append('num_clips', String(numClips))
  return api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress ? (progressEvent) => {
      const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
      onProgress(percentCompleted)
    } : undefined
  })
}

export const streamCleanedVideo = (jobId) => `/api/jobs/${jobId}/cleaned/stream`
export const downloadCleanedVideo = (jobId) => `/api/jobs/${jobId}/cleaned/download`

export const getJob = (jobId) => api.get(`/jobs/${jobId}`)

export const getJobClips = (jobId) => api.get(`/jobs/${jobId}/clips`)

export const deleteJob = (jobId) => api.delete(`/jobs/${jobId}`)

export const retryJob = (jobId) => api.post(`/jobs/${jobId}/retry`)

export const cancelJob = (jobId) => api.post(`/jobs/${jobId}/cancel`)

export const downloadClip = (clipId) => `/api/clips/${clipId}/download`

export const streamClip = (clipId) => `/api/clips/${clipId}/stream`

export default api
