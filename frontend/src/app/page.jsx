'use client'

import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'
import { useEffect } from 'react'

export default function Home() {
  const router = useRouter()
  const { isAuthenticated } = useAuthStore()

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/dashboard')
    }
  }, [isAuthenticated, router])

  return (
    <div className="min-h-screen bg-primary">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        {/* Hero Section */}
        <div className="text-center mb-20">
          <h1 className="text-5xl md:text-6xl font-bold text-white mb-6">
            Generate UML Diagrams from <span className="text-accent">User Stories</span>
          </h1>
          <p className="text-xl text-slate-400 mb-8 max-w-2xl mx-auto">
            Transform your user stories into beautiful UML diagrams automatically using AI-powered natural language processing.
          </p>

          <div className="flex gap-4 justify-center">
            <button
              onClick={() => router.push('/auth/login')}
              className="px-8 py-3 bg-accent text-white rounded-lg font-semibold hover:bg-blue-600 transition"
            >
              Login
            </button>
            <button
              onClick={() => router.push('/auth/register')}
              className="px-8 py-3 border-2 border-accent text-accent rounded-lg font-semibold hover:bg-accent hover:text-white transition"
            >
              Get Started
            </button>
          </div>
        </div>

        {/* Features */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-4xl mx-auto">
          <div className="bg-secondary rounded-lg p-8 text-center">
            <div className="text-4xl mb-4">📊</div>
            <h3 className="text-xl font-semibold text-white mb-2">Class Diagrams</h3>
            <p className="text-slate-400">Automatically extract classes and relationships from your stories</p>
          </div>

          <div className="bg-secondary rounded-lg p-8 text-center">
            <div className="text-4xl mb-4">🎯</div>
            <h3 className="text-xl font-semibold text-white mb-2">Use Case Diagrams</h3>
            <p className="text-slate-400">Visualize actors and their interactions with the system</p>
          </div>

          <div className="bg-secondary rounded-lg p-8 text-center">
            <div className="text-4xl mb-4">📈</div>
            <h3 className="text-xl font-semibold text-white mb-2">Sequence Diagrams</h3>
            <p className="text-slate-400">Model message flows and interactions between entities</p>
          </div>
        </div>

        {/* Features continued */}
        <div className="mt-8 bg-secondary rounded-lg p-8 max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold text-white mb-6 text-center">Why Choose UML Generator?</h2>
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <li className="flex items-start gap-4">
              <span className="text-accent text-2xl">✓</span>
              <div>
                <h4 className="font-semibold text-white mb-1">AI-Powered Analysis</h4>
                <p className="text-slate-400">Advanced NLP extracts entities and relationships automatically</p>
              </div>
            </li>
            <li className="flex items-start gap-4">
              <span className="text-accent text-2xl">✓</span>
              <div>
                <h4 className="font-semibold text-white mb-1">Multiple Diagram Types</h4>
                <p className="text-slate-400">Generate Class, Use Case, Sequence, and Activity diagrams</p>
              </div>
            </li>
            <li className="flex items-start gap-4">
              <span className="text-accent text-2xl">✓</span>
              <div>
                <h4 className="font-semibold text-white mb-1">Easy to Use</h4>
                <p className="text-slate-400">Simply write user stories and let AI do the heavy lifting</p>
              </div>
            </li>
            <li className="flex items-start gap-4">
              <span className="text-accent text-2xl">✓</span>
              <div>
                <h4 className="font-semibold text-white mb-1">Save & Share</h4>
                <p className="text-slate-400">Store your projects and diagrams in the cloud</p>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}
