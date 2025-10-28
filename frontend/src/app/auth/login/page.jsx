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
        router.push('/dashboard')
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
      <div className="min-h-screen bg-background flex items-center justify-center px-6">
        <div className="w-full max-w-md bg-primary border-2 border-border-color rounded-lg p-8">
          <h1 className="text-3xl font-bold text-center mb-8 text-accent">Login</h1>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-bold text-black mb-2">
                Username
              </label>
              <input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 bg-white border-2 border-border-color rounded-lg text-black placeholder-muted-text focus:outline-none focus:ring-2 focus:ring-accent font-semibold text-sm"
                placeholder="Enter your username"
              />
            </div>

            <div>
              <label className="block text-sm font-bold text-black mb-2">
                Password
              </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    required
                    className="w-full px-4 py-2 bg-white border-2 border-border-color rounded-lg text-black placeholder-muted-text focus:outline-none focus:ring-2 focus:ring-accent pr-10 font-semibold text-sm"
                    placeholder="Enter your password"
                  />
                  <button type="button" onClick={togglePassword} className="absolute right-3 top-2 text-muted-text hover:text-accent focus:outline-none">
                    {showPassword ? (
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 2.25 12c1.955 4.21 6.092 7.5 9.75 7.5 1.563 0 3.06-.362 4.396-1.02M19.07 16.95A10.45 10.45 0 0 0 21.75 12c-1.955-4.21-6.092-7.5-9.75-7.5a9.72 9.72 0 0 0-3.36.58M9.53 9.53a3 3 0 0 1 4.24 4.24m-4.24-4.24L4.5 4.5m9.24 9.24l6.26 6.26" />
                      </svg>
                    ) : (
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
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
              className="w-full bg-accent text-white font-bold py-2 px-4 rounded-lg border-2 border-accent hover:bg-background hover:text-accent transition text-sm disabled:bg-muted-text disabled:border-muted-text"
            >
              {isLoading ? 'Logging in...' : 'Login'}
            </button>
          </form>

          <p className="text-center text-muted-text mt-6 text-sm">
            Don&apos;t have an account?{' '}
            <Link href="/auth/register" className="text-accent font-bold hover:text-black transition">
              Register here
            </Link>
          </p>
        </div>
      </div>
    </>
  )
}
