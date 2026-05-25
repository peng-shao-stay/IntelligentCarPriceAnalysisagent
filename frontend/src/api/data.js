import api from './index'

export const fetchDataList = (params) => api.get('/data/list', { params })

export const fetchBrands = () => api.get('/data/brands')

export const getDataItem = (id) => api.get(`/data/${id}`)

export const updateDataItem = (id, data) => api.put(`/data/${id}`, data)

export const deleteDataItem = (id) => api.delete(`/data/${id}`)

export const batchDeleteItems = (ids) => api.post('/data/batch-delete', ids)
