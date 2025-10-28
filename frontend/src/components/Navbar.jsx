'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'
import { LogOut, Layout } from 'lucide-react'

export default function Navbar() {
  const router = useRouter()
  const { user, isAuthenticated, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    router.push('/')
  }

  return (
    <nav className="bg-primary border-b-2 border-border-color">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Logo */}
          <div className="flex items-center">
            <Link href="/" className="flex items-center space-x-2 text-accent hover:text-black transition font-bold text-lg">
              <Layout size={24} strokeWidth={2} />
              <span className="hidden sm:inline">UML Generator</span>
            </Link>
          </div>

          {/* Navigation */}
          <div className="flex items-center space-x-4">
            {isAuthenticated ? (
              <>
                <div className="text-black font-bold text-sm">
                  <span className="hidden sm:inline">Welcome, </span>
                  <span className="text-accent font-bold">{user?.username}</span>
                </div>
                <button
                  onClick={handleLogout}
                  className="flex items-center space-x-1 px-3 py-2 rounded-lg text-black border-2 border-border-color hover:bg-accent hover:text-white transition font-bold text-sm"
                >
                  <LogOut size={16} strokeWidth={2} />
                  <span className="hidden sm:inline">Logout</span>
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/auth/login"
                  className="px-3 py-2 rounded-lg text-black border-2 border-border-color hover:bg-accent hover:text-white transition font-bold text-sm"
                >
                  Login
                </Link>
                <Link
                  href="/auth/register"
                  className="px-3 py-2 bg-accent text-white rounded-lg border-2 border-accent font-bold text-sm hover:bg-primary hover:text-accent transition"
                >
                  Register
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  )
}
