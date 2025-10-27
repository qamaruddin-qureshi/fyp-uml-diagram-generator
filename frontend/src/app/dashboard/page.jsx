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
        router.push(`/projects/${response.project_id}`)
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
      <div className="min-h-screen bg-primary py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="mb-12">
            <h1 className="text-4xl font-bold text-white mb-2">Dashboard</h1>
            <p className="text-slate-400">Create and manage your UML diagram projects</p>
          </div>

          {/* Create Project Form */}
          <div className="bg-secondary rounded-lg shadow-lg p-8 mb-12">
            <h2 className="text-2xl font-bold text-white mb-6">Create New Project</h2>
            <form onSubmit={handleCreateProject} className="flex gap-4">
              <input
                type="text"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="Enter project name"
                className="flex-1 px-4 py-3 bg-primary border border-slate-600 rounded-md text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-accent"
              />
              <button
                type="submit"
                disabled={isCreating}
                className="bg-accent text-white px-6 py-3 rounded-md font-semibold hover:bg-blue-600 disabled:bg-slate-600 transition flex items-center gap-2"
              >
                <Plus size={20} />
                {isCreating ? 'Creating...' : 'Create'}
              </button>
            </form>
          </div>

          {/* Projects Grid */}
          <div>
            <h2 className="text-2xl font-bold text-white mb-6">Your Projects</h2>
            {projects.length === 0 ? (
              <div className="text-center py-12">
                <FileText size={48} className="mx-auto text-slate-500 mb-4" />
                <p className="text-slate-400 text-lg">No projects yet. Create one to get started!</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {projects.map((project) => (
                  <Link
                    key={project.ProjectID}
                    href={`/projects/${project.ProjectID}`}
                    className="bg-secondary rounded-lg shadow-lg p-6 hover:shadow-xl hover:border-accent border border-slate-700 transition cursor-pointer"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <FileText size={32} className="text-accent" />
                    </div>
                    <h3 className="text-xl font-semibold text-white mb-2 truncate">
                      {project.ProjectName}
                    </h3>
                    <p className="text-slate-400 text-sm">
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
