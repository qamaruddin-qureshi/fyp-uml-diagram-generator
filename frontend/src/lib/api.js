import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
}) 

// Add token to requests if it exists
apiClient.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle responses
apiClient.interceptors.response.use(
  (response) => {
    // If response has a 'data' property with success flag, extract it
    if (response.data && typeof response.data === 'object' && 'success' in response.data) {
      return response.data.data || response.data
    }
    return response.data
  },
  (error) => {
    if (error.response?.status === 401) {
      // Clear token and redirect to login
      if (typeof window !== 'undefined') {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        window.location.href = '/auth/login'
      }
    }
    return Promise.reject(error.response?.data || error)
  }
)

export const authAPI = {
  register: (username, password, confirmPassword) =>
    apiClient.post('/auth/register', { username, password, confirm_password: confirmPassword }),
  
  login: (username, password) =>
    apiClient.post('/auth/login', { username, password }),
  
  logout: () => apiClient.post('/auth/logout'),
}

export const projectAPI = {
  getAll: () => apiClient.get('/projects'),
  
  getById: (projectId) => apiClient.get(`/project/${projectId}`),
  
  create: (projectName) =>
    apiClient.post('/project/new', { project_name: projectName }),
  
  update: (projectId, { user_stories, diagram_type }) =>
    apiClient.post(`/project/${projectId}/update`, {
      user_stories,
      diagram_type,
    }),
}

export default apiClient
