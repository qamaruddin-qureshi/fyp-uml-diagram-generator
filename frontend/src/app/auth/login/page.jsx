'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { authAPI } from '@/lib/api'
import { useAuthStore } from '@/store/auth'
import toast, { Toaster } from 'react-hot-toast'

export default function LoginPage() {
  const router = useRouter()
  const { setToken, setUser } = useAuthStore()
  const [formData, setFormData] = useState({ username: '', password: '' })
  const [isLoading, setIsLoading] = useState(false)
    const [showPassword, setShowPassword] = useState(false)

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }
    const togglePassword = () => setShowPassword((prev) => !prev)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const response = await authAPI.login(formData.username, formData.password)
      
      if (response.success) {
        setToken(response.token || 'token')
        setUser({ username: formData.username, id: response.user_id })
        toast.success('Login successful!')
        router.push('/')
      } else {
        toast.error(response.message || 'Login failed')
      }
    } catch (error) {
      toast.error(error.message || 'An error occurred during login')
      console.error('Login error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <>
      <Toaster />
      <div className="min-h-screen bg-primary flex items-center justify-center px-4">
        <div className="w-full max-w-md bg-secondary rounded-lg shadow-lg p-8">
          <h1 className="text-3xl font-bold text-center mb-8 text-accent">Login</h1>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Username
              </label>
              <input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 bg-primary border border-slate-600 rounded-md text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-accent"
                placeholder="Enter your username"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Password
              </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    required
                    className="w-full px-4 py-2 bg-primary border border-slate-600 rounded-md text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-accent pr-10"
                    placeholder="Enter your password"
                  />
                  <button type="button" onClick={togglePassword} className="absolute right-2 top-2 text-slate-400 hover:text-accent focus:outline-none">
                    {showPassword ? (
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 2.25 12c1.955 4.21 6.092 7.5 9.75 7.5 1.563 0 3.06-.362 4.396-1.02M19.07 16.95A10.45 10.45 0 0 0 21.75 12c-1.955-4.21-6.092-7.5-9.75-7.5a9.72 9.72 0 0 0-3.36.58M9.53 9.53a3 3 0 0 1 4.24 4.24m-4.24-4.24L4.5 4.5m9.24 9.24l6.26 6.26" />
                      </svg>
                    ) : (
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12C4.205 7.79 8.342 4.5 12 4.5c3.658 0 7.795 3.29 9.75 7.5-1.955 4.21-6.092 7.5-9.75 7.5-3.658 0-7.795-3.29-9.75-7.5z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0z" />
                      </svg>
                    )}
                  </button>
                </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-accent text-white py-2 rounded-md font-semibold hover:bg-blue-600 disabled:bg-slate-600 transition"
            >
              {isLoading ? 'Logging in...' : 'Login'}
            </button>
          </form>

          <p className="text-center text-slate-400 mt-6">
            Don&apos;t have an account?{' '}
            <Link href="/auth/register" className="text-accent hover:text-blue-400">
              Register here
            </Link>
          </p>
        </div>
      </div>
    </>
  )
}
