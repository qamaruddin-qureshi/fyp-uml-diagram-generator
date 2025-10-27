import { create } from 'zustand'

export const useAuthStore = create((set) => ({
  user: typeof window !== 'undefined' ? JSON.parse(localStorage.getItem('user') || 'null') : null,
  isAuthenticated: typeof window !== 'undefined' ? !!localStorage.getItem('token') : false,
  
  setUser: (user) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('user', JSON.stringify(user))
    }
    set({ user, isAuthenticated: !!user })
  },
  
  setToken: (token) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('token', token)
    }
    set({ isAuthenticated: !!token })
  },
  
  logout: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    }
    set({ user: null, isAuthenticated: false })
  },
}))
