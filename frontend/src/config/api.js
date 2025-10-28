/**
 * API Configuration
 * Centralized configuration for API endpoints
 */

export const API_CONFIG = {
  // Backend API base URL
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000',
  
  // Enable/disable detailed logging
  debug: process.env.NODE_ENV === 'development',
}

export const getBackendUrl = () => API_CONFIG.baseURL

/**
 * Get the full URL for a static resource
 * @param {string} path - The path to the resource (e.g., '/static/image.png')
 * @returns {string} The full URL
 */
export const getStaticUrl = (path) => {
  const baseUrl = getBackendUrl()
  return `${baseUrl}${path}`
}

/**
 * Get the full URL for a download endpoint
 * @param {string} projectId - The project ID
 * @param {string} diagramType - The diagram type (class, use_case, sequence, activity)
 * @returns {string} The full download URL
 */
export const getDownloadUrl = (projectId, diagramType) => {
  const baseUrl = getBackendUrl()
  return `${baseUrl}/project/${projectId}/download/${diagramType}`
}

export default API_CONFIG
