import { create } from 'zustand'

export const useProjectStore = create((set) => ({
  projects: [],
  currentProject: null,
  
  setProjects: (projects) => set({ projects }),
  
  setCurrentProject: (project) => set({ currentProject: project }),
  
  addProject: (project) => set((state) => ({ 
    projects: [...state.projects, project] 
  })),
  
  updateProject: (projectId, updates) => set((state) => ({
    projects: state.projects.map((p) =>
      p.ProjectID === projectId ? { ...p, ...updates } : p
    ),
    currentProject: state.currentProject?.ProjectID === projectId 
      ? { ...state.currentProject, ...updates }
      : state.currentProject,
  })),
}))
