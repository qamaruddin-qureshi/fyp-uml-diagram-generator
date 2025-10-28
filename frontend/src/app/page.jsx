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
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <h1 className="text-5xl md:text-6xl font-bold text-black mb-6">
            Generate UML Diagrams from <span className="text-accent">User Stories</span>
          </h1>
          <p className="text-lg text-muted-text mb-8 max-w-2xl mx-auto font-semibold">
            Transform your user stories into beautiful UML diagrams automatically using AI-powered natural language processing.
          </p>

          <div className="flex gap-4 justify-center flex-col sm:flex-row">
            <button
              onClick={() => router.push('/auth/login')}
              className="px-8 py-3 bg-accent text-white rounded-lg font-bold border-2 border-accent hover:bg-background hover:text-accent transition text-base"
            >
              Login
            </button>
            <button
              onClick={() => router.push('/auth/register')}
              className="px-8 py-3 border-2 border-accent text-accent rounded-lg font-bold hover:bg-accent hover:text-white transition text-base"
            >
              Get Started
            </button>
          </div>
        </div>

        {/* Features */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-6xl mx-auto mb-8">
          <div className="bg-primary border-2 border-border-color rounded-lg p-6 text-center">
            <div className="text-4xl mb-4">📊</div>
            <h3 className="text-xl font-bold text-black mb-2">Class Diagrams</h3>
            <p className="text-muted-text text-sm font-semibold">Automatically extract classes and relationships from your stories</p>
          </div>

          <div className="bg-primary border-2 border-border-color rounded-lg p-6 text-center">
            <div className="text-4xl mb-4">🎯</div>
            <h3 className="text-xl font-bold text-black mb-2">Use Case Diagrams</h3>
            <p className="text-muted-text text-sm font-semibold">Visualize actors and their interactions with the system</p>
          </div>

          <div className="bg-primary border-2 border-border-color rounded-lg p-6 text-center">
            <div className="text-4xl mb-4">📈</div>
            <h3 className="text-xl font-bold text-black mb-2">Sequence Diagrams</h3>
            <p className="text-muted-text text-sm font-semibold">Model message flows and interactions between entities</p>
          </div>

          <div className="bg-primary border-2 border-border-color rounded-lg p-6 text-center">
            <div className="text-4xl mb-4">⚙️</div>
            <h3 className="text-xl font-bold text-black mb-2">Activity Diagrams</h3>
            <p className="text-muted-text text-sm font-semibold">Illustrate workflows and process flows in your system</p>
          </div>
        </div>

        {/* Features continued */}
        <div className="bg-primary border-2 border-border-color rounded-lg p-8 max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold text-black mb-6 text-center">Why Choose UML Generator?</h2>
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <li className="flex items-start gap-4">
              <span className="text-accent text-2xl font-bold">✓</span>
              <div>
                <h4 className="font-bold text-black mb-1">AI-Powered Analysis</h4>
                <p className="text-muted-text text-sm font-semibold">Advanced NLP extracts entities and relationships automatically</p>
              </div>
            </li>
            <li className="flex items-start gap-4">
              <span className="text-accent text-2xl font-bold">✓</span>
              <div>
                <h4 className="font-bold text-black mb-1">Multiple Diagram Types</h4>
                <p className="text-muted-text text-sm font-semibold">Generate Class, Use Case, Sequence, and Activity diagrams</p>
              </div>
            </li>
            <li className="flex items-start gap-4">
              <span className="text-accent text-2xl font-bold">✓</span>
              <div>
                <h4 className="font-bold text-black mb-1">Easy to Use</h4>
                <p className="text-muted-text text-sm font-semibold">Simply write user stories and let AI do the heavy lifting</p>
              </div>
            </li>
            <li className="flex items-start gap-4">
              <span className="text-accent text-2xl font-bold">✓</span>
              <div>
                <h4 className="font-bold text-black mb-1">Save & Share</h4>
                <p className="text-muted-text text-sm font-semibold">Store your projects and diagrams in the cloud</p>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}
