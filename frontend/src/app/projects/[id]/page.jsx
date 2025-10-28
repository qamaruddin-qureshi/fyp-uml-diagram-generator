'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Image from 'next/image'
import { projectAPI } from '@/lib/api'
import { useProjectStore } from '@/store/projects'
import toast, { Toaster } from 'react-hot-toast'
import { Zap, ArrowLeft } from 'lucide-react'

const DIAGRAM_TYPES = [
  { value: 'class', label: '📊 Class Diagram' },
  { value: 'use_case', label: '🎯 Use Case Diagram' },
  { value: 'sequence', label: '📈 Sequence Diagram' },
  { value: 'activity', label: '⚙️ Activity Diagram' },
]

export default function ProjectPage() {
  const router = useRouter()
  const params = useParams()
  const { currentProject, setCurrentProject } = useProjectStore()
  
  const [project, setProject] = useState(null)
  const [stories, setStories] = useState('')
  const [diagramType, setDiagramType] = useState('class')
  const [isLoading, setIsLoading] = useState(true)
  const [isUpdating, setIsUpdating] = useState(false)
  const [diagramUrl, setDiagramUrl] = useState(null)
  const [isClient, setIsClient] = useState(false)

  // Ensure client-side rendering
  useEffect(() => {
    setIsClient(true)
  }, [])

  useEffect(() => {
    const fetchProject = async () => {
      try {
        const data = await projectAPI.getById(params.id)
        setProject(data)
        setCurrentProject(data)
        setStories(data.stories_text || '')
        
        // Restore diagram type from localStorage
        const savedDiagramType = localStorage.getItem(`diagram_type_${params.id}`)
        if (savedDiagramType) {
          setDiagramType(savedDiagramType)
          // Build diagram URL with saved diagram type
          const timestamp = new Date().getTime()
          setDiagramUrl(`/static/${savedDiagramType}_${data.ProjectID}.png?t=${timestamp}`)
        } else {
          // Build diagram URL with default diagram type
          const timestamp = new Date().getTime()
          setDiagramUrl(`/static/class_${data.ProjectID}.png?t=${timestamp}`)
        }
      } catch (error) {
        toast.error('Failed to load project')
        console.error(error)
        router.push('/dashboard')
      } finally {
        setIsLoading(false)
      }
    }

    if (params.id && isClient) {
      fetchProject()
    }
  }, [params.id, router, setCurrentProject, isClient])

  const handleDiagramTypeChange = (e) => {
    const newType = e.target.value
    setDiagramType(newType)
    localStorage.setItem(`diagram_type_${params.id}`, newType)
    
    // Update diagram URL
    if (project?.ProjectID) {
      const timestamp = new Date().getTime()
      setDiagramUrl(`/static/${newType}_${project.ProjectID}.png?t=${timestamp}`)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!stories.trim()) {
      toast.error('Please enter at least one user story')
      return
    }

    setIsUpdating(true)
    try {
      const response = await projectAPI.update(params.id, {
        userStories: stories,
        diagramType,
      })

      if (response.success) {
        toast.success('Diagram updated successfully!')
        
        // Update diagram URL with new timestamp to force refresh
        const timestamp = new Date().getTime()
        setDiagramUrl(`/static/${diagramType}_${params.id}.png?t=${timestamp}`)
      } else {
        toast.error(response.message || 'Failed to update project')
      }
    } catch (error) {
      toast.error(error.message || 'Failed to update project')
      console.error(error)
    } finally {
      setIsUpdating(false)
    }
  }

  if (isLoading || !isClient) {
    return (
      <div className="min-h-screen bg-primary flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-accent mx-auto mb-4"></div>
          <p className="text-slate-300">Loading project...</p>
        </div>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="min-h-screen bg-primary flex items-center justify-center">
        <p className="text-slate-300">Project not found</p>
      </div>
    )
  }

  return (
    <>
      <Toaster />
      <div className="min-h-screen bg-primary py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-8 flex items-center justify-between">
            <div>
              <button
                onClick={() => router.push('/dashboard')}
                className="flex items-center gap-2 text-slate-400 hover:text-white transition mb-4"
              >
                <ArrowLeft size={20} />
                Back to Dashboard
              </button>
              <h1 className="text-4xl font-bold text-white">{project.ProjectName}</h1>
              <p className="text-slate-400 mt-2">Project ID: {project.ProjectID}</p>
            </div>
          </div>

          {/* Main Content */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Left Column - Editor */}
            <div className="bg-secondary rounded-lg shadow-lg p-8">
              <h2 className="text-2xl font-bold text-white mb-6">User Stories</h2>

              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Stories Input */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Enter your user stories (one per line)
                  </label>
                  <textarea
                    value={stories}
                    onChange={(e) => setStories(e.target.value)}
                    placeholder="As a user, I want to...&#10;As a customer, I want to...&#10;As an admin, I want to..."
                    rows={8}
                    className="w-full px-4 py-3 bg-primary border border-slate-600 rounded-md text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-accent resize-none"
                  />
                </div>

                {/* Diagram Type Selector */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Diagram Type
                  </label>
                  <select
                    value={diagramType}
                    onChange={handleDiagramTypeChange}
                    className="w-full px-4 py-2 bg-primary border border-slate-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-accent"
                  >
                    {DIAGRAM_TYPES.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                  <small className="block text-slate-400 mt-2">
                    Current: <span className="text-accent font-semibold">{diagramType}</span>
                  </small>
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={isUpdating}
                  className="w-full bg-accent text-white py-3 rounded-md font-semibold hover:bg-blue-600 disabled:bg-slate-600 transition flex items-center justify-center gap-2"
                >
                  <Zap size={20} />
                  {isUpdating ? 'Generating...' : 'Generate / Update Diagram'}
                </button>
              </form>
            </div>

            {/* Right Column - Diagram */}
            <div className="bg-secondary rounded-lg shadow-lg p-8">
              <h2 className="text-2xl font-bold text-white mb-6">Generated Diagram</h2>

              <div className="bg-primary rounded-md overflow-hidden flex items-center justify-center min-h-96">
                {diagramUrl ? (
                  <div className="w-full relative">
                    <Image
                      src={diagramUrl}
                      alt="Generated UML Diagram"
                      width={800}
                      height={600}
                      className="w-full h-auto"
                      unoptimized
                      onError={() => {
                        setDiagramUrl(null)
                      }}
                    />
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <div className="text-slate-500 text-4xl mb-4">📊</div>
                    <p className="text-slate-400">No diagram generated yet.</p>
                    <p className="text-slate-500 text-sm mt-2">
                      Add some user stories and select a diagram type to get started.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
