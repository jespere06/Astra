import { useState, useEffect, useRef, useCallback } from 'react'
import { learningService } from './services/learningService'
import { ReviewView } from './ReviewView'
import { TrainingWizard } from './components/TrainingWizard'
import { DatasetReadinessReport } from './components/DatasetReadinessReport'
import './index.css'

/* ========================================
   CONFIG / API LAYER
   ======================================== */
const API = {
  orchestrator: '/api/orchestrator',
  ingest: '/api/ingest',
  core: '/api/core',
}

async function apiFetch(base, path, options = {}) {
  try {
    const res = await fetch(`${base}${path}`, {
      headers: { 'Authorization': `Bearer dev-token`, ...options.headers },
      ...options,
    })
    if (!res.ok) {
      const err = await res.text()
      throw new Error(`HTTP ${res.status}: ${err}`)
    }
    return res.json()
  } catch (e) {
    console.error(`[API] ${base}${path} →`, e.message)
    return null
  }
}

/* ========================================
   ICON COMPONENTS (inline SVGs)
   ======================================== */
const Icon = ({ d, size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
)

const Icons = {
  Library: () => <Icon d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />,
  Play: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><polygon points="10 8 16 12 10 16 10 8" fill="currentColor" stroke="none" />
    </svg>
  ),
  Clock: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  Shield: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><polyline points="9 12 11 14 15 10" />
    </svg>
  ),
  Settings: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  Database: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </svg>
  ),
  Upload: () => <Icon d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" />,
  FileText: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  ),
  Activity: () => <Icon d="M22 12h-4l-3 9L9 3l-3 9H2" />,
  Cpu: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2" ry="2" /><rect x="9" y="9" width="6" height="6" /><line x1="9" y1="1" x2="9" y2="4" /><line x1="15" y1="1" x2="15" y2="4" /><line x1="9" y1="20" x2="9" y2="23" /><line x1="15" y1="20" x2="15" y2="23" /><line x1="20" y1="9" x2="23" y2="9" /><line x1="20" y1="14" x2="23" y2="14" /><line x1="1" y1="9" x2="4" y2="9" /><line x1="1" y1="14" x2="4" y2="14" />
    </svg>
  ),
  ChevronRight: () => <Icon d="M9 18l6-6-6-6" size={16} />,
  Check: () => <Icon d="M20 6L9 17l-5-5" />,
  AlertCircle: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  ),
  Download: () => <Icon d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />,
  Trash: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  ),
  Loader: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="icon-spin">
      <line x1="12" y1="2" x2="12" y2="6" /><line x1="12" y1="18" x2="12" y2="22" /><line x1="4.93" y1="4.93" x2="7.76" y2="7.76" /><line x1="16.24" y1="16.24" x2="19.07" y2="19.07" /><line x1="2" y1="12" x2="6" y2="12" /><line x1="18" y1="12" x2="22" y2="12" /><line x1="4.93" y1="19.07" x2="7.76" y2="16.24" /><line x1="16.24" y1="7.76" x2="19.07" y2="4.93" />
    </svg>
  ),
  Zap: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  ),
  Youtube: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22.54 6.42a2.78 2.78 0 0 0-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 0 0-1.94 2A29 29 0 0 0 1 11.75a29 29 0 0 0 .46 5.33A2.78 2.78 0 0 0 3.4 19c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 0 0 1.94-2 29 29 0 0 0 .46-5.25 29 29 0 0 0-.46-5.33z" />
      <polygon points="9.75 15.02 15.5 11.75 9.75 8.48 9.75 15.02" fill="currentColor" stroke="none" />
    </svg>
  ),
  Plus: () => <Icon d="M12 5v14M5 12h14" />,
}

/* ========================================
   SIDEBAR COMPONENT
   ======================================== */
function Sidebar({ activeView, onViewChange, serviceStatus }) {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__logo">A</div>
        <div>
          <div className="sidebar__title">ASTRA</div>
          <div className="sidebar__subtitle">Municipal AI</div>
        </div>
      </div>

      <nav className="sidebar__nav">
        <NavItem icon={<Icons.Library />} label="Historical Ingest" active={activeView === 'INGEST'} onClick={() => onViewChange('INGEST')} />
        <NavItem icon={<Icons.Zap />} label="Training Data" active={activeView === 'TRAINING'} onClick={() => onViewChange('TRAINING')} />
        <NavItem icon={<Icons.Check />} label="Review" active={activeView === 'REVIEW'} onClick={() => onViewChange('REVIEW')} />
        <NavItem icon={<Icons.Play />} label="Orchestrator" active={activeView === 'ORCH'} onClick={() => onViewChange('ORCH')} />
        <NavItem icon={<Icons.Clock />} label="Archive" active={activeView === 'ARCHIVE'} onClick={() => onViewChange('ARCHIVE')} />
      </nav>

      <div className="sidebar__footer">
        <div className="service-status-panel">
          <div className="service-dot-row">
            <span className={`service-dot ${serviceStatus.core ? 'service-dot--ok' : 'service-dot--err'}`} />
            <span className="service-dot-label">Core Engine</span>
          </div>
          <div className="service-dot-row">
            <span className={`service-dot ${serviceStatus.orchestrator ? 'service-dot--ok' : 'service-dot--err'}`} />
            <span className="service-dot-label">Orchestrator</span>
          </div>
          <div className="service-dot-row">
            <span className={`service-dot ${serviceStatus.ingest ? 'service-dot--ok' : 'service-dot--err'}`} />
            <span className="service-dot-label">Ingest</span>
          </div>
        </div>
      </div>
    </aside>
  )
}

function NavItem({ icon, label, active, onClick }) {
  return (
    <button className={`nav-item ${active ? 'nav-item--active' : ''}`} onClick={onClick}>
      <span className="nav-item__icon">{icon}</span>
      <span>{label}</span>
    </button>
  )
}

/* ========================================
   REUSABLE COMPONENTS
   ======================================== */
function StatCard({ icon, label, value, meta, delay, variant }) {
  return (
    <div className={`stat-card animate-in delay-${delay} ${variant ? `stat-card--${variant}` : ''}`}>
      <div className="stat-card__label">
        <span className="stat-card__label-icon">{icon}</span>
        {label}
      </div>
      <div className="stat-card__value">{value}</div>
      {meta && <div className="stat-card__meta">{meta}</div>}
    </div>
  )
}

function Card({ title, icon, children, actions, delay = 1 }) {
  return (
    <div className={`card animate-in delay-${delay}`}>
      <div className="card__header">
        <div className="card__title">
          {icon && <span className="card__title-icon">{icon}</span>}
          {title}
        </div>
        {actions && <div className="card__actions">{actions}</div>}
      </div>
      {children}
    </div>
  )
}

function Toast({ message, type, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4000)
    return () => clearTimeout(t)
  }, [onClose])

  return (
    <div className={`toast toast--${type}`}>
      {type === 'success' ? <Icons.Check /> : <Icons.AlertCircle />}
      <span>{message}</span>
    </div>
  )
}

/* ========================================
   INGEST VIEW (Real file upload)
   ======================================== */
function IngestView({ addToast, addToArchive }) {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState([])
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef(null)

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragActive(false)
    const dropped = Array.from(e.dataTransfer.files).filter(f => f.name.endsWith('.docx'))
    if (dropped.length === 0) {
      addToast('Solo se aceptan archivos .docx', 'error')
      return
    }
    setFiles(prev => [...prev, ...dropped])
  }, [addToast])

  const onFileSelect = (e) => {
    const selected = Array.from(e.target.files).filter(f => f.name.endsWith('.docx'))
    setFiles(prev => [...prev, ...selected])
  }

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (files.length === 0) return
    setUploading(true)
    const newResults = []

    for (const file of files) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('tenant_id', 'concejo_manizales')

      try {
        const res = await fetch(`${API.ingest}/v1/ingest`, {
          method: 'POST',
          body: formData,
        })
        const data = await res.json()

        if (res.ok) {
          newResults.push({ name: file.name, status: 'success', data })
          addToArchive({
            name: file.name,
            skeleton_id: data.skeleton_id,
            assets: data.assets_extracted,
            date: new Date().toISOString(),
            type: 'ingest',
          })
        } else {
          newResults.push({ name: file.name, status: 'error', error: data.detail || 'Error desconocido' })
        }
      } catch (err) {
        newResults.push({ name: file.name, status: 'error', error: err.message })
      }
    }

    setResults(newResults)
    setFiles([])
    setUploading(false)

    const successes = newResults.filter(r => r.status === 'success').length
    if (successes > 0) addToast(`${successes}/${newResults.length} archivos procesados`, 'success')
    if (successes < newResults.length) addToast(`${newResults.length - successes} archivos fallaron`, 'error')
  }

  return (
    <div className="content-wrapper">
      <div className="stats-grid">
        <StatCard icon={<Icons.Database />} label="Tenant Active" value="Manizales" meta="concejo_manizales" delay={1} />
        <StatCard icon={<Icons.Library />} label="Queued Files" value={files.length} meta="Ready for ingestion" delay={2} />
        <StatCard icon={<Icons.Shield />} label="Processed" value={results.filter(r => r.status === 'success').length} meta="This batch" delay={3} />
      </div>

      <Card title="Document Ingestion" icon={<Icons.Upload />} delay={4}>
        <div
          className={`dropzone ${dragActive ? 'dropzone--active' : ''}`}
          onDrop={onDrop}
          onDragOver={(e) => { e.preventDefault(); setDragActive(true) }}
          onDragLeave={() => setDragActive(false)}
          onClick={() => fileInputRef.current?.click()}
        >
          <input ref={fileInputRef} type="file" accept=".docx" multiple hidden onChange={onFileSelect} />
          <div className="dropzone__icon-wrap">
            <span className="dropzone__icon"><Icons.FileText /></span>
          </div>
          <div className="dropzone__title">Drop your .docx files here</div>
          <div className="dropzone__subtitle">
            ASTRA will extract the skeleton, process assets, and index the document into the knowledge base
          </div>
        </div>

        {files.length > 0 && (
          <div className="file-list">
            {files.map((f, i) => (
              <div key={i} className="file-list__item">
                <div className="file-list__item-left">
                  <Icons.FileText />
                  <span className="file-list__name">{f.name}</span>
                  <span className="file-list__size">{(f.size / 1024).toFixed(0)} KB</span>
                </div>
                <button className="file-list__remove" onClick={(e) => { e.stopPropagation(); removeFile(i) }}>
                  <Icons.Trash />
                </button>
              </div>
            ))}
            <button
              className="btn btn--primary btn--full"
              onClick={handleUpload}
              disabled={uploading}
            >
              {uploading ? (
                <><Icons.Loader /> Processing {files.length} file(s)...</>
              ) : (
                <>Start Teaching ASTRA ({files.length} file{files.length > 1 ? 's' : ''})</>
              )}
            </button>
          </div>
        )}
      </Card>

      {results.length > 0 && (
        <Card title="Ingestion Results" icon={<Icons.Activity />} delay={1}>
          <div className="results-list">
            {results.map((r, i) => (
              <div key={i} className={`result-item result-item--${r.status}`}>
                <div className="result-item__icon">
                  {r.status === 'success' ? <Icons.Check /> : <Icons.AlertCircle />}
                </div>
                <div className="result-item__info">
                  <div className="result-item__name">{r.name}</div>
                  <div className="result-item__detail">
                    {r.status === 'success'
                      ? `Skeleton ID: ${r.data.skeleton_id} · ${r.data.assets_extracted} assets`
                      : r.error}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

/* ========================================
   ORCHESTRATION VIEW (Real session mgmt)
   ======================================== */
function OrchestrationView({ addToast, addToArchive, serviceStatus }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [transcriptLines, setTranscriptLines] = useState([])
  const timerRef = useRef(null)

  // Timer
  useEffect(() => {
    if (session) {
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    }
    return () => clearInterval(timerRef.current)
  }, [session])

  const formatTime = (s) => {
    const h = String(Math.floor(s / 3600)).padStart(2, '0')
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0')
    const sec = String(s % 60).padStart(2, '0')
    return `${h}:${m}:${sec}`
  }

  const startSession = async () => {
    setLoading(true)
    const res = await apiFetch(API.orchestrator, '/v1/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tenant_id: 'concejo_manizales',
        skeleton_id: 'skel_default',
        client_timezone: 'America/Bogota',
        metadata: { numero_acta: `Acta-${Date.now().toString(36)}`, presidente: 'Presidente del Concejo' }
      }),
    })

    if (res) {
      setSession(res)
      setElapsed(0)
      setTranscriptLines([])
      addToast(`Sesión iniciada: ${res.session_id?.slice(0, 8)}...`, 'success')
    } else {
      addToast('Error al iniciar sesión. ¿Está el Orchestrator activo?', 'error')
    }
    setLoading(false)
  }

  const finalizeSession = async () => {
    if (!session) return
    setLoading(true)
    const res = await apiFetch(API.orchestrator, `/v1/session/${session.session_id}/finalize`, {
      method: 'POST',
    })

    if (res) {
      addToast('Sesión finalizada. Acta generada.', 'success')
      addToArchive({
        name: `Acta-${session.session_id?.slice(0, 8)}`,
        date: new Date().toISOString(),
        type: 'session',
        session_id: session.session_id,
        duration: formatTime(elapsed),
      })
    } else {
      addToast('Error al finalizar sesión. Puede estar en draining.', 'error')
    }

    clearInterval(timerRef.current)
    setSession(null)
    setElapsed(0)
    setLoading(false)
  }

  const discardSession = () => {
    clearInterval(timerRef.current)
    setSession(null)
    setElapsed(0)
    setTranscriptLines([])
  }

  return (
    <div className="content-wrapper">
      <div className="page-header">
        <h2 className="page-header__title">Session Orchestrator</h2>
        <span className={`status-badge ${serviceStatus.orchestrator ? 'status-badge--online' : 'status-badge--offline'}`}>
          <span className="status-badge__dot" />
          {serviceStatus.orchestrator ? 'Engine Online' : 'Engine Offline'}
        </span>
      </div>

      <div className="orch-grid">
        <div>
          <Card title="Active Live Session" icon={<Icons.Play />} delay={1}>
            {!session ? (
              <div className="session-empty">
                <div className="session-empty__icon"><Icons.Play /></div>
                <div className="session-empty__title">No active session</div>
                <div className="session-empty__desc">
                  Start a new session to begin recording and transcribing a municipal act
                </div>
                <button className="btn btn--primary btn--lg" onClick={startSession} disabled={loading}>
                  {loading ? <><Icons.Loader /> Connecting...</> : 'Create New Session'}
                </button>
              </div>
            ) : (
              <div>
                <div className="session-info-bar">
                  <div>
                    <div className="session-info-bar__label">Session ID</div>
                    <div className="session-info-bar__value session-info-bar__value--primary">
                      {session.session_id?.slice(0, 18)}...
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div className="session-info-bar__label">Elapsed</div>
                    <div className="session-info-bar__value">{formatTime(elapsed)}</div>
                  </div>
                </div>

                {/* Audio upload section */}
                <AudioUploader sessionId={session.session_id} addToast={addToast} onTranscript={(line) => setTranscriptLines(prev => [...prev, line])} />

                <div className="transcript-console">
                  {transcriptLines.length === 0 && (
                    <span className="transcript-console__placeholder">
                      Awaiting audio input... Upload audio chunks to see transcription here.
                    </span>
                  )}
                  {transcriptLines.map((line, i) => (
                    <div key={i}>
                      <span className="transcript-console__ts">[{line.ts}]</span>{' '}
                      <span className="transcript-console__speaker">{line.speaker}:</span>{' '}
                      {line.text}
                    </div>
                  ))}
                  <span className="transcript-console__cursor" />
                </div>

                <div className="session-actions">
                  <button className="btn btn--primary" style={{ flex: 1 }} onClick={finalizeSession} disabled={loading}>
                    {loading ? <><Icons.Loader /> Finalizing...</> : 'Finalize & Build Acta'}
                  </button>
                  <button className="btn btn--ghost" onClick={discardSession}>Discard</button>
                </div>
              </div>
            )}
          </Card>
        </div>

        <div className="orch-grid__sidebar">
          <Card title="System Health" icon={<Icons.Cpu />} delay={2}>
            <ServiceHealthPanel status={serviceStatus} />
          </Card>

          <Card title="Session Info" icon={<Icons.Activity />} delay={3}>
            {session ? (
              <div className="session-detail-panel">
                <div className="session-detail-row">
                  <span className="session-detail-key">Tenant</span>
                  <span className="session-detail-val">{session.tenant_id || 'concejo_manizales'}</span>
                </div>
                <div className="session-detail-row">
                  <span className="session-detail-key">Status</span>
                  <span className="session-detail-val session-detail-val--live">{session.status || 'OPEN'}</span>
                </div>
                <div className="session-detail-row">
                  <span className="session-detail-key">Duration</span>
                  <span className="session-detail-val">{formatTime(elapsed)}</span>
                </div>
                <div className="session-detail-row">
                  <span className="session-detail-key">Chunks Sent</span>
                  <span className="session-detail-val">{transcriptLines.length}</span>
                </div>
              </div>
            ) : (
              <div className="session-detail-panel">
                <p className="text-muted">No active session</p>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}

/* ========================================
   AUDIO UPLOADER (Chunk upload for sessions)
   ======================================== */
function AudioUploader({ sessionId, addToast, onTranscript }) {
  const [uploading, setUploading] = useState(false)
  const seqRef = useRef(1)

  const handleAudioUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('sequence_id', seqRef.current++)

    try {
      const res = await fetch(`${API.orchestrator}/v1/session/${sessionId}/append`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()

      if (res.ok) {
        const now = new Date()
        onTranscript({
          ts: `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`,
          speaker: 'AUDIO',
          text: `Chunk ${seqRef.current - 1} accepted (block: ${data.block_id?.slice(0, 8) || 'N/A'})`,
        })
        addToast(`Audio chunk accepted`, 'success')
      } else {
        addToast(`Error: ${data.detail || 'Upload failed'}`, 'error')
      }
    } catch (err) {
      addToast(`Connection error: ${err.message}`, 'error')
    }

    setUploading(false)
    e.target.value = ''
  }

  return (
    <div className="audio-uploader">
      <label className="btn btn--ghost btn--sm" style={{ cursor: uploading ? 'wait' : 'pointer' }}>
        {uploading ? <><Icons.Loader /> Sending...</> : <><Icons.Upload /> Upload Audio Chunk</>}
        <input type="file" accept="audio/*" hidden onChange={handleAudioUpload} disabled={uploading} />
      </label>
    </div>
  )
}

/* ========================================
   SERVICE HEALTH PANEL
   ======================================== */
function ServiceHealthPanel({ status }) {
  const services = [
    { name: 'Core Engine', key: 'core', detail: status.coreVersion || '—' },
    { name: 'Orchestrator', key: 'orchestrator', detail: status.orchVersion || '—' },
    { name: 'Ingest Service', key: 'ingest', detail: 'v1' },
  ]

  return (
    <div className="health-panel">
      {services.map(s => (
        <div className="health-row" key={s.key}>
          <div className="health-row__left">
            <span className={`service-dot ${status[s.key] ? 'service-dot--ok' : 'service-dot--err'}`} />
            <span>{s.name}</span>
          </div>
          <span className="health-row__detail">{status[s.key] ? s.detail : 'Offline'}</span>
        </div>
      ))}
    </div>
  )
}

/* ========================================
   ARCHIVE VIEW (Real history)
   ======================================== */
function ArchiveView({ archive }) {
  return (
    <div className="content-wrapper">
      <div className="page-header">
        <h2 className="page-header__title">Archive</h2>
        <span className="status-badge status-badge--online">
          <span className="status-badge__dot" />
          {archive.length} Records
        </span>
      </div>

      {archive.length === 0 ? (
        <Card title="No Records Yet" icon={<Icons.Clock />} delay={1}>
          <div className="session-empty">
            <div className="session-empty__icon"><Icons.Clock /></div>
            <div className="session-empty__title">Archive is empty</div>
            <div className="session-empty__desc">
              Ingested documents and finalized sessions will appear here
            </div>
          </div>
        </Card>
      ) : (
        <Card title="Document & Session History" icon={<Icons.Library />} delay={1}>
          <div className="archive-table">
            <div className="archive-table__header">
              <span>Name</span>
              <span>Type</span>
              <span>Date</span>
              <span>Details</span>
            </div>
            {archive.map((item, i) => (
              <div className="archive-table__row" key={i}>
                <span className="archive-table__name">
                  <Icons.FileText />
                  {item.name}
                </span>
                <span>
                  <span className={`type-badge type-badge--${item.type}`}>
                    {item.type === 'ingest' ? 'Ingested' : 'Session'}
                  </span>
                </span>
                <span className="archive-table__date">
                  {new Date(item.date).toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' })}
                </span>
                <span className="archive-table__detail">
                  {item.type === 'ingest'
                    ? `${item.assets} assets · ID: ${item.skeleton_id}`
                    : `${item.duration || '—'} · ${item.session_id?.slice(0, 8) || ''}`}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

/* ========================================
   TRAINING VIEW (New Module)
   ======================================== */


function TrainingView({ addToast }) {
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  
  // Load from API
  const loadSessions = async () => {
    try {
      setIsLoading(true)
      const data = await learningService.getSessions()
      setSessions(data)
    } catch (e) {
      console.error("Failed to load sessions", e)
      addToast('Error loading sessions: ' + e.message, 'error')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadSessions()
  }, [])

  const createSession = async () => {
    const name = `Training Session ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString()}`
    try {
      const newSession = await learningService.createSession(name)
      setSessions(prev => [newSession, ...prev])
      setActiveSessionId(newSession.id)
      addToast('New training session created', 'success')
    } catch (e) {
      addToast('Failed to create session: ' + e.message, 'error')
    }
  }

  const deleteSession = async (id) => {
    if (window.confirm("Delete this session?")) {
      try {
        await learningService.deleteSession(id)
        setSessions(prev => prev.filter(s => s.id !== id))
        if (activeSessionId === id) setActiveSessionId(null)
        addToast('Session deleted', 'info')
      } catch (e) {
        addToast('Failed to delete session: ' + e.message, 'error')
      }
    }
  }

  const activeSession = sessions.find(s => s.id === activeSessionId)

  const updateSession = async (id, newSessionData) => {
    // Optimistic update
    setSessions(prev => prev.map(s => s.id === id ? { ...s, ...newSessionData } : s))
    
    // Persist if rows changed
    if (newSessionData.rows) {
        try {
            await learningService.updateSessionRows(id, newSessionData.rows)
        } catch (e) {
            console.error("Failed to save rows", e)
            addToast('Warning: Changes not saved to backend', 'error')
        }
    }
  }

  return (
    <div className="content-wrapper">
      <div className="page-header">
        <h2 className="page-header__title">AI Training Module</h2>
        <div className="page-header__actions">
          {!activeSessionId && (
            <button className="btn btn--primary" onClick={createSession}>
              <Icons.Plus /> New Session
            </button>
          )}
        </div>
      </div>

      {!activeSessionId ? (
        <div className="sessions-grid">
           {sessions.length === 0 ? (
             <Card title="No Sessions" icon={<Icons.Zap />} delay={1}>
               <div className="session-empty">
                 <div className="session-empty__icon"><Icons.Zap /></div>
                 <div className="session-empty__title">Start Teaching ASTRA</div>
                 <div className="session-empty__desc">
                   Create a session to map YouTube audio to Official DOCX records.
                 </div>
                 <button className="btn btn--primary" onClick={createSession}>Create First Session</button>
               </div>
             </Card>
           ) : (
             <div className="card-grid">
               {sessions.map(s => (
                 <div key={s.id} className="session-card animate-in" onClick={() => setActiveSessionId(s.id)}>
                    <div className="session-card__icon"><Icons.Zap /></div>
                    <div className="session-card__info">
                      <div className="session-card__title">{s.name}</div>
                      <div className="session-card__meta">
                        {s.rows.length} rows · {new Date(s.created).toLocaleDateString()}
                      </div>
                    </div>
                    <button className="session-card__del" onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}>
                      <Icons.Trash />
                    </button>
                 </div>
               ))}
             </div>
           )}
        </div>
      ) : (
        <TrainingSessionDetail 
          session={activeSession} 
          onBack={() => setActiveSessionId(null)}
          onUpdate={(data) => updateSession(activeSession.id, data)}
          addToast={addToast}
        />
      )}
    </div>
  )
}

// Helper: extract a short label from a filename or path
const extractActaLabel = (name) => {
  if (!name) return null
  const basename = name.split('/').pop().split('\\').pop()
  return basename.replace(/\.(docx|txt)$/i, '').trim()
}

// Helper: extract YouTube video ID for thumbnail
const getYtVideoId = (url) => {
  if (!url) return null
  const match = url.match(/[?&]v=([a-zA-Z0-9_-]{11})/) || url.match(/youtu\.be\/([a-zA-Z0-9_-]{11})/)
  return match ? match[1] : null
}

// Extracted Row Component — card-based layout
const TrainingRow = ({ row, index, onUpdate, onDelete, addToast }) => {
  const handleDrop = async (e) => {
     e.preventDefault()
     const file = e.dataTransfer.files[0]
     if (file && (file.name.endsWith('.docx') || file.name.endsWith('.pdf'))) {
       try {
         // Optimistic UI
         onUpdate(row.id, 'docx', { name: file.name, size: file.size, uploading: true })
         addToast('Subiendo archivo...', 'info')

         // Get Presigned URL
         const { upload_url, s3_key } = await learningService.getPresignedUrl(file.name, file.type)
         
         // Upload to S3
         await learningService.uploadToS3(upload_url, file)
         
         // Success
         onUpdate(row.id, 'docx', { 
             name: file.name, 
             size: file.size, 
             s3_key: s3_key, 
             uploading: false 
         })
         addToast('Archivo subido correctamente', 'success')
       } catch (err) {
         console.error(err)
         addToast('Error al subir: ' + err.message, 'error')
         onUpdate(row.id, 'docx', null)
       }
     } else {
       addToast('Solo archivos .docx o .pdf permitidos', 'error')
     }
  }

  const videoId = getYtVideoId(row.ytUrl)
  const actaLabel = row.docx ? extractActaLabel(row.docx.name) : (row.actaName ? extractActaLabel(row.actaName) : null)

  const statusConfig = {
    idle: { color: 'var(--text-2)', label: 'Pendiente' },
    downloading: { color: 'var(--accent-amber)', label: 'Descargando…' },
    transcribing: { color: 'var(--secondary)', label: 'Transcribiendo…' },
    ready: { color: 'var(--primary)', label: 'Listo' },
    training: { color: 'var(--accent-green)', label: 'Entrenando…' },
    done: { color: 'var(--accent-green)', label: 'Completo' },
  }
  const st = statusConfig[row.status] || statusConfig.idle

  return (
    <div className="tr-card">
      <div className="tr-card__num">{String(index + 1).padStart(2, '0')}</div>

      {/* YouTube Section */}
      <div className="tr-card__yt">
        {row.ytUrl ? (
          <div className="tr-card__yt-body">
            {videoId && (
              <img 
                className="tr-card__thumb" 
                src={`https://img.youtube.com/vi/${videoId}/mqdefault.jpg`} 
                alt="thumb"
                onError={(e) => { e.target.style.display = 'none' }}
              />
            )}
            <div className="tr-card__yt-info">
              <a href={row.ytUrl} target="_blank" rel="noreferrer" className="tr-card__yt-link">
                {row.ytUrl}
              </a>
              <div className="tr-card__tag tr-card__tag--ok">✓ Link</div>
            </div>
          </div>
        ) : (
          <div className="tr-card__yt-empty">
            <Icons.Youtube />
            <input 
              type="text" 
              placeholder="Pegar URL de YouTube" 
              value={row.ytUrl} 
              onChange={(e) => onUpdate(row.id, 'ytUrl', e.target.value)}
              className="tr-card__yt-input"
            />
          </div>
        )}
      </div>

      {/* Arrow */}
      <div className="tr-card__arrow">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
      </div>

      {/* Acta / Ground Truth Section */}
      <div 
        className={`tr-card__acta ${!row.docx && !actaLabel ? 'tr-card__acta--empty' : ''}`}
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
      >
        {actaLabel ? (
          <div className="tr-card__acta-body">
            <Icons.FileText />
            <span className="tr-card__acta-name" title={actaLabel}>{actaLabel}</span>
            {row.docx && (
              <button className="tr-card__acta-remove" onClick={() => onUpdate(row.id, 'docx', null)}>×</button>
            )}
          </div>
        ) : (
          <div className="tr-card__acta-drop">
            <Icons.FileText />
            <span>Soltar .docx</span>
          </div>
        )}
      </div>

      {/* Status */}
      <div className="tr-card__status">
        <div className="tr-card__status-dot" style={{ background: st.color }} />
        <span className="tr-card__status-label">{st.label}</span>
        {row.progress > 0 && row.progress < 100 && (
          <div className="tr-card__progress">
            <div className="tr-card__progress-fill" style={{ width: `${row.progress}%` }} />
          </div>
        )}
      </div>

      {/* Delete */}
      <button className="tr-card__del" onClick={() => onDelete(row.id)} title="Eliminar">
        <Icons.Trash />
      </button>
    </div>
  )
}

function TrainingSessionDetail({ session, onBack, onUpdate, addToast }) {
  const fileInputRef = useRef(null)
  const [showWizard, setShowWizard] = useState(false)
  const [reportData, setReportData] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [hasCachedPrep, setHasCachedPrep] = useState(false)

  // Detect cached preparation data when opening wizard
  const openWizard = () => {
    const hasReadyRows = session.rows.some(r => r.status === 'ready' || r.status === 'done')
    setHasCachedPrep(hasReadyRows)
    setShowWizard(true)
  }

  const addRow = () => {
    const newRow = {
      id: Date.now().toString(36),
      ytUrl: '',
      actaName: '',
      docx: null,
      status: 'idle',
      progress: 0
    }
    onUpdate({ rows: [...session.rows, newRow] })
  }

  const updateRow = (rowId, field, value) => {
    const updatedRows = session.rows.map(r => r.id === rowId ? { ...r, [field]: value } : r)
    onUpdate({ rows: updatedRows })
  }

  const deleteRow = (rowId) => {
    const newRows = session.rows.filter(r => r.id !== rowId)
    onUpdate({ rows: newRows })
  }

  const handleCsvImport = (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (evt) => {
      const text = evt.target.result
      const lines = text.split(/\r?\n/).filter(l => l.trim().length > 0)
      
      const header = lines[0].toLowerCase()
      const isOptimized = header.includes('archivo') && header.includes('link')

      const parseLine = (line) => {
        const res = []
        let cur = ''
        let inQuote = false
        for (let i = 0; i < line.length; i++) {
            const char = line[i]
            if (char === '"') { inQuote = !inQuote }
            else if (char === ',' && !inQuote) { res.push(cur); cur = '' }
            else { cur += char }
        }
        res.push(cur)
        return res
      }

      const rowsToMap = isOptimized ? lines.slice(1) : lines
      
      const newRows = rowsToMap.map(line => {
        if (isOptimized) {
           const columns = parseLine(line)
           const archivo = columns[0]?.trim()
           const link = columns[3]?.trim()
           if (!archivo && !link) return null
           return { id: Math.random().toString(36).substr(2, 9), ytUrl: link || '', actaName: archivo || '', docx: null, status: 'idle', progress: 0 }
        } else {
           const columns = line.split(',')
           if (columns.length < 1) return null
           return { id: Math.random().toString(36).substr(2, 9), ytUrl: columns[0]?.trim() || '', actaName: '', docx: columns[1] ? { name: columns[1].trim(), size: 0 } : null, status: 'idle', progress: 0 }
        }
      }).filter(r => r !== null)
      
      onUpdate({ rows: [...session.rows, ...newRows] })
      addToast(`Importadas ${newRows.length} filas del CSV`, 'success')
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  // Job Polling
  const [activeJobId, setActiveJobId] = useState(null)
  const pollingRef = useRef(null)

  useEffect(() => {
    return () => {
        if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [])

  const startPolling = (jobId) => {
    if (pollingRef.current) clearInterval(pollingRef.current)
    setActiveJobId(jobId)

    pollingRef.current = setInterval(async () => {
        try {
            const status = await learningService.getJobStatus(jobId)
            
            // Actualizar filas en la UI (progreso)
            if (status.rows && Array.isArray(status.rows)) {
                const updatedRows = session.rows.map(r => {
                    const update = status.rows.find(u => u.id === r.id)
                    return update ? { ...r, ...update } : r
                })
                onUpdate({ rows: updatedRows })
            }

            // --- CAMBIO AQUÍ: Detectar finalización y abrir reporte ---
            if (status.state === 'COMPLETED' || status.state === 'FAILED') {
                clearInterval(pollingRef.current)
                setActiveJobId(null)
                
                if (status.state === 'COMPLETED') {
                    addToast('Procesamiento finalizado exitosamente', 'success')
                    
                    // Si el backend devolvió estadísticas de alineación, abrimos el reporte
                    if (status.alignment_stats) {
                        setReportData({
                            structural_coverage_pct: status.alignment_stats.structural_coverage_pct,
                            total_aligned_pairs: status.alignment_stats.aligned_pairs || 0,
                            static_nodes: 15, // Estos puedes dejarlos mock por ahora
                            dynamic_nodes: 5,
                            // USA LOS DATOS REALES QUE VIENEN DEL BACKEND
                            sample_pairs: status.alignment_stats.sample_pairs || [] 
                        })
                    }
                } else {
                    addToast(`Falló el procesamiento: ${status.error || 'Error desconocido'}`, 'error')
                }
            }
            // ----------------------------------------------------------

        } catch (e) {
            console.error("Polling error", e)
        }
    }, 2000)
  }

  const handleWizardConfirm = async (mode) => {
    // For full training with cache, use ALL rows (ready + idle)
    // For prep-only or no-cache, only use idle rows
    const useCache = mode === 'FULL_TRAINING' && hasCachedPrep
    const rowsToProcess = useCache
      ? session.rows.filter(r => r.status === 'idle' || r.status === 'ready')
      : session.rows.filter(r => r.status === 'idle')

    if (rowsToProcess.length === 0) {
      addToast('No hay filas pendientes para procesar', 'info')
      setShowWizard(false)
      return
    }

    setProcessing(true)
    try {
        addToast('Guardando sesión...', 'info')
        await learningService.updateSessionRows(session.id, session.rows)
        
        const payload = {
            session_id: session.id,
            rows: rowsToProcess,
            config: {
              execution_mode: mode,
              resume_from_cache: useCache,
            }
        }
        
        const response = await learningService.triggerTraining(payload)
        setShowWizard(false)

        if (mode === 'DATA_PREP_ONLY' && response.report) {
            setReportData(response.report)
            addToast('Análisis de dataset completado', 'success')
        } else if (response.job_id) {
            addToast(
              useCache
                ? 'Retomando desde caché — entrenamiento iniciado en RunPod'
                : 'Entrenamiento iniciado en RunPod',
              'success'
            )
            startPolling(response.job_id)
        } else {
             addToast('Respuesta del servidor incompleta', 'warning')
        }
    } catch (e) {
        addToast('Error al iniciar proceso: ' + e.message, 'error')
    } finally {
        setProcessing(false)
    }
  }

  const totalRows = session.rows.length
  const withYt = session.rows.filter(r => r.ytUrl).length
  const withActa = session.rows.filter(r => r.docx || r.actaName).length

  return (
    <div className="session-detail">
       <button className="btn btn--ghost mb-4" onClick={onBack}>← Volver a Sesiones</button>
       
       <div className="tr-stats">
         <div className="tr-stat">
           <span className="tr-stat__val">{totalRows}</span>
           <span className="tr-stat__label">Filas</span>
         </div>
         <div className="tr-stat">
           <span className="tr-stat__val tr-stat__val--green">{withYt}</span>
           <span className="tr-stat__label">Con YouTube</span>
         </div>
         <div className="tr-stat">
           <span className="tr-stat__val tr-stat__val--purple">{withActa}</span>
           <span className="tr-stat__label">Con Acta</span>
         </div>
       </div>

       <Card title={session.name} icon={<Icons.Zap />} actions={
         <div className="flex gap-2">
            <input type="file" accept=".csv" ref={fileInputRef} hidden onChange={handleCsvImport} />
            <button className="btn btn--ghost btn--sm" onClick={() => fileInputRef.current?.click()}>Importar CSV</button>
            <button className="btn btn--primary btn--sm" onClick={openWizard}>Procesar</button>
         </div>
       }>
          <div className="training-grid-v2">
             <div className="training-rows-v2">
               {session.rows.length === 0 ? (
                 <div className="tr-empty">
                   <Icons.FileText />
                   <span>Importa un CSV o agrega filas manualmente</span>
                 </div>
               ) : (
                 session.rows.map((row, idx) => (
                   <TrainingRow 
                      key={row.id} 
                      row={row}
                      index={idx}
                      onUpdate={updateRow}
                      onDelete={deleteRow}
                      addToast={addToast}
                   />
                 ))
               )}
             </div>
             
             <button className="btn btn--ghost btn--full mt-4" onClick={addRow}>
               <Icons.Plus /> Agregar Fila
             </button>
          </div>
       </Card>

       {showWizard && (
           <TrainingWizard 
               onConfirm={handleWizardConfirm}
               onCancel={() => setShowWizard(false)}
               loading={processing}
                hasCachedPreparation={hasCachedPrep}
           />
       )}

       {reportData && (
           <DatasetReadinessReport 
               metrics={reportData}
               onClose={() => setReportData(null)}
           />
       )}
    </div>
  )
}


/* ========================================
   APP ROOT
   ======================================== */
function App() {
  const [activeView, setActiveView] = useState('INGEST')
  const [toasts, setToasts] = useState([])
  const [archive, setArchive] = useState([])
  const [serviceStatus, setServiceStatus] = useState({ core: false, orchestrator: false, ingest: false })

  // Health check polling
  useEffect(() => {
    const checkHealth = async () => {
      const [core, orch, ingest] = await Promise.all([
        apiFetch(API.core, '/health').then(r => r).catch(() => null),
        apiFetch(API.orchestrator, '/health').then(r => r).catch(() => null),
        // Ingest doesn't have /health, check base
        fetch(`${API.ingest}/v1/ingest`, { method: 'OPTIONS' }).then(() => true).catch(() => null),
      ])

      setServiceStatus({
        core: !!core,
        coreVersion: core?.version || '',
        orchestrator: !!orch,
        orchVersion: orch?.version || 'v1',
        ingest: !!ingest,
      })
    }

    checkHealth()
    const interval = setInterval(checkHealth, 15000)
    return () => clearInterval(interval)
  }, [])

  const addToast = useCallback((message, type = 'info') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const addToArchive = useCallback((item) => {
    setArchive(prev => [item, ...prev])
  }, [])

  return (
    <div className="app-layout">
      <div className="ambient-blur ambient-blur--cyan" />
      <div className="ambient-blur ambient-blur--purple" />
      <div className="ambient-blur ambient-blur--green" />

      <Sidebar activeView={activeView} onViewChange={setActiveView} serviceStatus={serviceStatus} />

      <main className="main-content">
        {activeView === 'INGEST' && <IngestView addToast={addToast} addToArchive={addToArchive} />}
        {activeView === 'TRAINING' && <TrainingView addToast={addToast} />}
        {activeView === 'REVIEW' && <ReviewView addToast={addToast} />}
        {activeView === 'ORCH' && <OrchestrationView addToast={addToast} addToArchive={addToArchive} serviceStatus={serviceStatus} />}
        {activeView === 'ARCHIVE' && <ArchiveView archive={archive} />}
      </main>

      <div className="toast-container">
        {toasts.map(t => (
          <Toast key={t.id} message={t.message} type={t.type} onClose={() => removeToast(t.id)} />
        ))}
      </div>
    </div>
  )
}

export default App
