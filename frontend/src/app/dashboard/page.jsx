'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { projectAPI } from '@/lib/api'
import { useAuthStore } from '@/store/auth'
import { useProjectStore } from '@/store/projects'
import toast, { Toaster } from 'react-hot-toast'
import { Plus, FileText } from 'lucide-react'

export default function DashboardPage() {
  const router = useRouter()
  const { isAuthenticated } = useAuthStore()
  const { projects, setProjects, addProject } = useProjectStore()
  const [isLoading, setIsLoading] = useState(true)
  const [newProjectName, setNewProjectName] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [isClient, setIsClient] = useState(false)

  useEffect(() => {
    setIsClient(true)
  }, [])

  useEffect(() => {
    if (!isClient) return
    
    if (!isAuthenticated) {
      router.push('/auth/login')
      return
    }

    const fetchProjects = async () => {
      try {
        const data = await projectAPI.getAll()
        setProjects(data)
      } catch (error) {
        toast.error('Failed to load projects')
        console.error(error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchProjects()
  }, [isAuthenticated, router, setProjects, isClient])

  const handleCreateProject = async (e) => {
    e.preventDefault()

    if (!newProjectName.trim()) {
      toast.error('Please enter a project name')
      return
    }

    setIsCreating(true)
    try {
      const response = await projectAPI.create(newProjectName)
      
      if (response.success) {
        const newProject = {
          ProjectID: response.project_id,
          ProjectName: newProjectName,
          UserID: response.user_id,
        }
        addProject(newProject)
        setNewProjectName('')
        toast.success('Project created successfully!')
      } else {
        toast.error(response.message || 'Failed to create project')
      }
    } catch (error) {
      toast.error(error.message || 'Failed to create project')
      console.error(error)
    } finally {
      setIsCreating(false)
    }
  }

  if (!isClient || isLoading) {
    return (
      <div className="min-h-screen bg-primary flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-accent mx-auto mb-4"></div>
          <p className="text-slate-300">Loading projects...</p>
        </div>
      </div>
    )
  }

  return (
    <>
      <Toaster />
      <div className="min-h-screen bg-background py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="mb-12">
            <h1 className="text-4xl font-bold text-black mb-2">Dashboard</h1>
            <p className="text-lg text-muted-text">Create and manage your UML diagram projects</p>
          </div>

          {/* Create Project Form */}
          <div className="bg-primary border-2 border-border-color rounded-lg p-8 mb-12">
            <h2 className="text-2xl font-bold text-black mb-6">Create New Project</h2>
            <form onSubmit={handleCreateProject} className="flex gap-4 flex-col sm:flex-row">
              <input
                type="text"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="Enter project name"
                className="flex-1 px-4 py-2 bg-white border-2 border-border-color rounded-lg text-black placeholder-muted-text focus:outline-none focus:ring-2 focus:ring-accent font-semibold text-sm"
              />
              <button
                type="submit"
                disabled={isCreating}
                className="bg-accent text-white px-6 py-2 rounded-lg font-bold border-2 border-accent hover:bg-background hover:text-accent transition flex items-center gap-2 text-sm whitespace-nowrap disabled:bg-muted-text"
              >
                <Plus size={18} strokeWidth={2} />
                {isCreating ? 'Creating...' : 'Create'}
              </button>
            </form>
          </div>

          {/* Projects Grid */}
          <div>
            <h2 className="text-2xl font-bold text-black mb-6">Your Projects</h2>
            {projects.length === 0 ? (
              <div className="text-center py-12">
                <FileText size={48} className="mx-auto text-border-color mb-4" strokeWidth={1.5} />
                <p className="text-muted-text text-lg font-bold">No projects yet. Create one to get started!</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {projects.map((project) => (
                  <Link
                    key={project.ProjectID}
                    href={`/projects/${project.ProjectID}`}
                    className="bg-primary border-2 border-border-color rounded-lg p-6 hover:border-accent hover:shadow-lg transition cursor-pointer"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <FileText size={32} className="text-accent" strokeWidth={2} />
                    </div>
                    <h3 className="text-xl font-bold text-black mb-2 truncate">
                      {project.ProjectName}
                    </h3>
                    <p className="text-muted-text text-sm font-semibold">
                      ID: {project.ProjectID.slice(0, 8)}...
                    </p>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
