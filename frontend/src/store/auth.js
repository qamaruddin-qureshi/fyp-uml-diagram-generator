import { create } from 'zustand'

const getInitialState = () => {
  // This function is only called on client-side after hydration
  if (typeof window === 'undefined') {
    return {
      user: null,
      isAuthenticated: false,
    }
  }

  let user = null;
  try {
    const storedUser = localStorage.getItem('user');
    if (storedUser && storedUser !== 'undefined' && storedUser !== 'null') {
      user = JSON.parse(storedUser);
    }
  } catch (error) {
    console.error('Failed to parse stored user:', error);
    localStorage.removeItem('user'); // Clear corrupted data
  }

  return {
    user,
    isAuthenticated: !!localStorage.getItem('token'),
  }
}

export const useAuthStore = create((set) => {
  const initialState = getInitialState()

  return {
    user: initialState.user,
    isAuthenticated: initialState.isAuthenticated,
    
    setUser: (user) => {
      if (typeof window !== 'undefined') {
        if (user) {
          localStorage.setItem('user', JSON.stringify(user))
        } else {
          localStorage.removeItem('user')
        }
      }
      set({ user, isAuthenticated: !!user })
    },
    
    setToken: (token) => {
      if (typeof window !== 'undefined') {
        if (token) {
          localStorage.setItem('token', token)
        } else {
          localStorage.removeItem('token')
        }
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
  }
})

