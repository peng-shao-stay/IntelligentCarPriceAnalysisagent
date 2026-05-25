import api from './index'

export const fetchMCPServers = () => api.get('/admin/mcp/servers')

export const createMCPServer = (data) => api.post('/admin/mcp/servers', data)

export const updateMCPServer = (id, data) => api.put(`/admin/mcp/servers/${id}`, data)

export const deleteMCPServer = (id) => api.delete(`/admin/mcp/servers/${id}`)

export const testMCPConnection = (id) => api.post(`/admin/mcp/servers/${id}/test`)

export const fetchMCPTools = (id) => api.get(`/admin/mcp/servers/${id}/tools`)

export const discoverMCPTools = (id) => api.post(`/admin/mcp/servers/${id}/discover`)
