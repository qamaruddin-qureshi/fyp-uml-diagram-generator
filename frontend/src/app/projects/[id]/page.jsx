'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Image from 'next/image'
import { projectAPI } from '@/lib/api'
import { useProjectStore } from '@/store/projects'
import toast, { Toaster } from 'react-hot-toast'
import { Zap, ArrowLeft, Download } from 'lucide-react'

const DIAGRAM_TYPES = [
  { value: 'class', label: '📊 Class Diagram' },
  { value: 'use_case', label: '🎯 Use Case Diagram' },
  { value: 'sequence', label: '📈 Sequence Diagram' },
  { value: 'activity', label: '⚙️ Activity Diagram' },
  { value: 'component', label: '🧩 Component Diagram' },
  { value: 'deployment', label: '🚀 Deployment Diagram' },
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

        // Get backend URL
        const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'

        // Restore diagram type from localStorage
        const savedDiagramType = localStorage.getItem(`diagram_type_${params.id}`)
        if (savedDiagramType) {
          setDiagramType(savedDiagramType)
          // Build diagram URL with saved diagram type
          const timestamp = new Date().getTime()
          setDiagramUrl(`${backendUrl}/static/${savedDiagramType}_${data.ProjectID}.png?t=${timestamp}`)
        } else {
          // Build diagram URL with default diagram type
          const timestamp = new Date().getTime()
          setDiagramUrl(`${backendUrl}/static/class_${data.ProjectID}.png?t=${timestamp}`)
        }
      } catch (error) {
        console.error('Error loading project:', error)
        // Only redirect if it's a 401 or authentication error
        if (error?.response?.status === 401 || error?.status === 401) {
          toast.error('Your session has expired. Please log in again.')
          // Let the API client handle the redirect
        } else {
          toast.error('Failed to load project. Please try again.')
          console.error('Project loading error details:', error)
        }
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
      const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'
      const timestamp = new Date().getTime()
      setDiagramUrl(`${backendUrl}/static/${newType}_${project.ProjectID}.png?t=${timestamp}`)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    // Check if architectural diagram requires narration
    const isArchitecturalDiagram = diagramType === 'component' || diagramType === 'deployment'

    if (isArchitecturalDiagram && !stories.trim()) {
      toast.error(`Please enter architecture context for ${diagramType} diagram`)
      return
    }

    if (!isArchitecturalDiagram && !stories.trim()) {
      toast.error('Please enter at least one user story')
      return
    }

    setIsUpdating(true)
    try {
      // For architectural diagrams, send stories as user_narration
      const response = await projectAPI.update(params.id, {
        user_stories: isArchitecturalDiagram ? '' : stories,
        diagram_type: diagramType,
        user_narration: isArchitecturalDiagram ? stories : ''
      })

      if (response.success) {
        toast.success('Diagram updated successfully!')

        // Update diagram URL with new timestamp to force refresh
        const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'
        const timestamp = new Date().getTime()
        setDiagramUrl(`${backendUrl}/static/${diagramType}_${params.id}.png?t=${timestamp}`)
      } else {
        // Handle architecture context missing error
        if (response.error_code === 'ARCH_CONTEXT_MISSING') {
          toast.error(response.message + '\n\n' + response.suggestion, { duration: 6000 })
        } else {
          toast.error(response.message || 'Failed to update project')
        }
      }
    } catch (error) {
      toast.error(error.message || 'Failed to update project')
      console.error(error)
    } finally {
      setIsUpdating(false)
    }
  }

  const handleDownloadPDF = async () => {
    try {
      if (!diagramUrl) {
        toast.error('No diagram available to download. Generate one first.')
        return
      }

      const loadingToast = toast.loading('Generating PDF...')

      // Get the backend URL from the API client config
      const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'

      // Call the backend API to download PDF with credentials
      const response = await fetch(`${backendUrl}/project/${params.id}/download/${diagramType}`, {
        method: 'GET',
        credentials: 'include',  // Include cookies for authentication
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        toast.dismiss(loadingToast)
        try {
          const error = await response.json()
          toast.error(error.message || `Failed to download PDF (HTTP ${response.status})`)
        } catch {
          toast.error(`Failed to download PDF (HTTP ${response.status})`)
        }
        return
      }

      // Get the filename from Content-Disposition header if available
      const contentDisposition = response.headers.get('content-disposition')
      let filename = `diagram_${diagramType}.pdf`
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+)"/)
        if (filenameMatch) {
          filename = filenameMatch[1]
        }
      }

      // Create a blob and download
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      // Dismiss loading toast and show success
      toast.dismiss(loadingToast)
      toast.success('PDF downloaded successfully!')
    } catch (error) {
      toast.error(error.message || 'Failed to download PDF')
      console.error('Download error:', error)
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
      <div className="min-h-screen bg-background py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-8 flex items-center justify-between">
            <div>
              <button
                onClick={() => router.push('/dashboard')}
                className="flex items-center gap-2 text-accent hover:text-black transition mb-4 font-bold text-sm border-2 border-border-color px-3 py-2 rounded-lg"
              >
                <ArrowLeft size={18} strokeWidth={2} />
                Back to Dashboard
              </button>
              <h1 className="text-4xl font-bold text-black">{project.ProjectName}</h1>
            </div>
          </div>

          {/* Main Content */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Left Column - Editor */}
            <div className="bg-primary border-2 border-border-color rounded-lg p-8">
              <h2 className="text-2xl font-bold text-black mb-6">User Stories</h2>

              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Stories Input */}
                <div>
                  <label className="block text-sm font-bold text-black mb-2">
                    {diagramType === 'component' || diagramType === 'deployment'
                      ? `Enter Architecture Context for ${diagramType === 'component' ? 'Component' : 'Deployment'} Diagram`
                      : 'Enter your user stories (one per line)'}
                  </label>
                  <textarea
                    value={stories}
                    onChange={(e) => setStories(e.target.value)}
                    placeholder={
                      diagramType === 'component'
                        ? "Describe your system components:\nThe system consists of a React Frontend, Flask Backend API, and PostgreSQL Database. The Frontend communicates with the Backend API via REST. The Backend connects to the Database for data storage. We also integrate with Stripe payment gateway as an external service."
                        : diagramType === 'deployment'
                          ? "Describe your deployment architecture:\nThe Frontend is deployed in a Docker container. The Backend API runs on a Web Server. The PostgreSQL database runs on a Database Server. Users access the system through a Web Browser."
                          : "As a user, I want to...&#10;As a customer, I want to...&#10;As an admin, I want to..."
                    }
                    rows={8}
                    className="w-full px-4 py-2 bg-white border-2 border-border-color rounded-lg text-black placeholder-muted-text focus:outline-none focus:ring-2 focus:ring-accent resize-none font-semibold text-sm"
                  />
                  {(diagramType === 'component' || diagramType === 'deployment') && (
                    <small className="block text-muted-text mt-2 font-bold text-xs">
                      💡 Tip: Describe components, technologies, and how they interact. Be specific about deployment environments.
                    </small>
                  )}
                </div>

                {/* Diagram Type Selector */}
                <div>
                  <label className="block text-sm font-bold text-black mb-2">
                    Diagram Type
                  </label>
                  <select
                    value={diagramType}
                    onChange={handleDiagramTypeChange}
                    className="w-full px-4 py-2 bg-white border-2 border-border-color rounded-lg text-black focus:outline-none focus:ring-2 focus:ring-accent font-semibold text-sm"
                  >
                    {DIAGRAM_TYPES.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                  <small className="block text-muted-text mt-2 font-bold text-xs">
                    Current: <span className="text-accent font-bold text-sm">{diagramType}</span>
                  </small>
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={isUpdating}
                  className="w-full bg-accent text-white font-bold py-2 px-4 rounded-lg border-2 border-accent hover:bg-background hover:text-accent transition flex items-center justify-center gap-2 text-sm disabled:bg-muted-text"
                >
                  <Zap size={18} strokeWidth={2} />
                  {isUpdating ? 'Generating...' : 'Generate / Update Diagram'}
                </button>
              </form>
            </div>

            {/* Right Column - Diagram */}
            <div className="bg-primary border-2 border-border-color rounded-lg p-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-black">Generated Diagram</h2>
                {diagramUrl && (
                  <button
                    onClick={handleDownloadPDF}
                    className="flex items-center gap-2 bg-accent text-white font-bold py-2 px-4 rounded-lg border-2 border-accent hover:bg-background hover:text-accent transition text-sm"
                    title="Download diagram as PDF"
                  >
                    <Download size={18} strokeWidth={2} />
                    Download PDF
                  </button>
                )}
              </div>

              <div className="bg-white border-2 border-border-color rounded-lg overflow-hidden flex items-center justify-center min-h-96">
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
                    <div className="text-accent text-4xl mb-4 font-bold">📊</div>
                    <p className="text-black font-bold text-lg">No diagram generated yet.</p>
                    <p className="text-muted-text text-sm mt-2 font-semibold">
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
