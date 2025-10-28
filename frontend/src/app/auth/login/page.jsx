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

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

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
              <input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 bg-primary border border-slate-600 rounded-md text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-accent"
                placeholder="Enter your password"
              />
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
