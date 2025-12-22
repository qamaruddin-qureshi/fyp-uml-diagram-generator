import axios from 'axios'

// Create an axios instance with default config
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Important for handling session cookies/CORS
})

// Auth API endpoints
export const authAPI = {
  login: async (username, password) => {
    try {
      const response = await api.post('/auth/login', { username, password })
      return response.data
    } catch (error) {
      throw error.response?.data || error.message
    }
  },
  
  register: async (username, password, confirmPassword) => {
    try {
      // Note: Backend expects 'confirm_password', frontend sends 'confirmPassword'
      const response = await api.post('/auth/register', { 
        username, 
        password, 
        confirm_password: confirmPassword 
      })
      return response.data
    } catch (error) {
      throw error.response?.data || error.message
    }
  },

  logout: async () => {
    try {
      const response = await api.get('/auth/logout')
      return response.data
    } catch (error) {
      throw error.response?.data || error.message
    }
  }
}

// Project API endpoints
export const projectAPI = {
  getAll: async () => {
    try {
      const response = await api.get('/projects')
      return response.data
    } catch (error) {
      throw error.response?.data || error.message
    }
  },

  create: async (projectName) => {
    try {
      const response = await api.post('/project/new', { project_name: projectName })
      return response.data
    } catch (error) {
      throw error.response?.data || error.message
    }
  },

  getById: async (id) => {
    try {
      const response = await api.get(`/project/${id}`)
      return response.data
    } catch (error) {
      throw error.response?.data || error.message
    }
  },

  update: async (id, data) => {
    try {
      const response = await api.post(`/project/${id}/update`, data)
      return response.data
    } catch (error) {
      throw error.response?.data || error.message
    }
  }
}

export default api
