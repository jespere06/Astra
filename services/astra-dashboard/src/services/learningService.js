/**
 * ASTRA Learning Service
 * Handles communication with the astra-learn backend via API Gateway.
 */

const API_BASE = '/api/learning'

// Dev JWT signed with secret: "dev_secret_key_change_in_prod"
// Payload: { "tenant_id": "concejo_manizales", "sub": "admin-dev" }
const DEV_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJjb25jZWpvX21hbml6YWxlcyIsInN1YiI6ImFkbWluLWRldiJ9.sbCSEsN3CZBFz9Ca3jw32cHhX1EF68cVfj65CmrNUxM'

// Helper to get headers with Auth
const getHeaders = () => {
    const token = localStorage.getItem('astra_token') || DEV_TOKEN
    return {
        'Content-Type': 'application/json',
        'X-Tenant-Id': 'concejo_manizales',
        'Authorization': `Bearer ${token}`
    }
}

// Helper for handling API responses
const handleResponse = async (response) => {
    if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}))
        const message = errorBody.detail || errorBody.message || `API Error: ${response.status}`
        throw new Error(message)
    }
    return response.json()
}

export const learningService = {
    // --- SESSIONS ---

    /**
     * Get all training sessions
     * @returns {Promise<Array>} List of sessions
     */
    getSessions: async () => {
        const response = await fetch(`${API_BASE}/sessions`, {
            headers: getHeaders()
        })
        return handleResponse(response)
    },

    /**
     * Create a new training session
     * @param {string} name - Session name
     * @returns {Promise<Object>} Created session
     */
    createSession: async (name) => {
        const response = await fetch(`${API_BASE}/sessions`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ name })
        })
        return handleResponse(response)
    },

    /**
     * Delete a session
     * @param {string} sessionId 
     */
    deleteSession: async (sessionId) => {
        const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
            method: 'DELETE',
            headers: getHeaders()
        })
        if (!response.ok) throw new Error('Failed to delete session')
        return true
    },

    /**
     * Update session rows (save changes)
     * @param {string} sessionId 
     * @param {Array} rows 
     */
    updateSessionRows: async (sessionId, rows) => {
        const response = await fetch(`${API_BASE}/sessions/${sessionId}/rows`, {
            method: 'PUT',
            headers: getHeaders(),
            body: JSON.stringify({ rows })
        })
        return handleResponse(response)
    },

    // --- STORAGE (S3) ---

    /**
     * Get a presigned URL for uploading a file directly to S3
     * @param {string} filename 
     * @param {string} fileType 
     * @returns {Promise<{upload_url: string, s3_key: string}>}
     */
    getPresignedUrl: async (filename, fileType) => {
        const response = await fetch(`${API_BASE}/storage/presign`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ filename, content_type: fileType })
        })
        return handleResponse(response)
    },

    /**
     * Upload a file to S3 using a presigned URL
     * @param {string} uploadUrl 
     * @param {File} file 
     */
    uploadToS3: async (uploadUrl, file) => {
        const response = await fetch(uploadUrl, {
            method: 'PUT',
            headers: {
                'Content-Type': file.type
            },
            body: file
        })
        if (!response.ok) throw new Error('Failed to upload file to storage')
        return true
    },

    // --- JOBS (TRAINING) ---

    /**
     * Trigger a new training/mining job
     * Routes to the Orchestrator which handles the full pipeline.
     * @param {Object} payload - { rows, config: { execution_mode, resume_from_cache } }
     * @returns {Promise<{job_id: string, status: string}>}
     */
    triggerTraining: async (payload) => {
        // MANTENER LOS IDs Y ESTADOS PARA EL TRACKING VISUAL
        const validRows = payload.rows.filter(r => r.ytUrl && r.ytUrl.length > 0)

        const orchestratorPayload = {
            tenant_id: 'concejo_manizales', // TODO: obtain from AuthContext
            rows: validRows, // <-- AHORA ENVIAMOS LAS FILAS COMPLETAS
            execution_mode: payload.config.execution_mode,
            training_config: {
                resume_from_cache: payload.config.resume_from_cache || false,
            }
        }

        const response = await fetch(`/api/orchestrator/v1/training/train`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(orchestratorPayload)
        })
        return handleResponse(response)
    },

    /**
     * Get updated status of a running job
     * CORREGIDO: Ahora consulta al Orchestrator que es el dueño del Job.
     */
    getJobStatus: async (jobId) => {
        // 1. Apuntar al endpoint del Orchestrator
        const response = await fetch(`/api/orchestrator/v1/training/jobs/${jobId}`, {
            headers: getHeaders()
        })
        
        const data = await handleResponse(response)

        // 2. Normalizar respuesta para la UI (App.jsx espera 'state', backend manda 'status')
        // El backend devuelve: { job_id, status: "MINING", result_summary: {...}, rows: [...] }
        return {
            id: data.job_id,
            state: data.status, // Mapeo crítico: status -> state
            rows: data.rows,    // <-- AÑADIDO PARA LA UI
            // Si el trabajo terminó, result_summary puede tener datos útiles
            ...data.result_summary 
        }
    },

    // --- REVIEWS (HUMAN-IN-THE-LOOP) ---

    /**
     * Get pending reviews for a tenant
     * @param {string} tenantId 
     */
    getPendingReviews: async (tenantId) => {
        const response = await fetch(`/api/review/pending/${tenantId}`, {
            headers: getHeaders()
        })
        return handleResponse(response)
    },

    /**
     * Resolve a review item
     * @param {string} queueId 
     * @param {string} decision "APPROVE" | "REJECT" | "EDIT"
     * @param {Object} extras { edited_text, new_start, new_end }
     */
    resolveReview: async (queueId, decision, extras = {}) => {
        const response = await fetch(`/api/review/resolve`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({
                queue_id: queueId,
                decision,
                ...extras
            })
        })
        return handleResponse(response)
    }
}
