import axios from 'axios'

const apiClient = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, ''),
  timeout: 30000,
})

function unwrap(response) {
  return response.data
}

export const api = {
  getMaterials: () => apiClient.get('/api/materials').then(unwrap),
  uploadMaterial: (file) => {
    const data = new FormData()
    data.append('file', file)
    return apiClient.post('/api/upload', data).then(unwrap)
  },
  ask: (question) => apiClient.post('/api/ask', { question }).then(unwrap),
  generateAssessment: (topic = null, limit = 3) =>
    apiClient.post('/api/assessment/generate', { topic: topic || null, limit }).then(unwrap),
  submitAssessment: (questionId, studentAnswer) =>
    apiClient.post('/api/assessment/submit', {
      question_id: questionId,
      student_answer: studentAnswer,
    }).then(unwrap),
  getMastery: () => apiClient.get('/api/learner/mastery').then(unwrap),
  getWeakTopics: () => apiClient.get('/api/learner/weak-topics').then(unwrap),
  getRecommendations: () => apiClient.get('/api/learner/recommendations').then(unwrap),
}

export function getApiError(error) {
  if (error.response?.data?.detail) return error.response.data.detail
  if (error.code === 'ECONNABORTED') return 'The backend took too long to respond. Please try again.'
  if (error.request) {
    return 'Could not reach the NovaMind API. Check that the backend is running and VITE_API_BASE_URL is correct.'
  }
  return error.message || 'Something went wrong. Please try again.'
}