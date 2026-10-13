
import { useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  Check,
  FileText,
  FileUp,
  FileVideo,
  Presentation,
  RotateCw,
} from 'lucide-react'
import EmptyState from '../components/EmptyState.jsx'
import { api, getApiError } from '../services/api.js'

function formatDate(value) {
  if (!value) return 'Date unavailable'

  const date = new Date(value)

  return Number.isNaN(date.getTime())
    ? 'Date unavailable'
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
      }).format(date)
}

function MaterialIcon({ type }) {
  if (type === 'pptx') return <Presentation size={17} />
  if (type === 'mp4') return <FileVideo size={17} />
  return <FileText size={17} />
}

export default function Materials() {
  const inputRef = useRef(null)

  const [materials, setMaterials] = useState([])
  const [selectedFile, setSelectedFile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function loadMaterials() {
    setLoading(true)
    setError('')

    try {
      setMaterials(await api.getMaterials())
    } catch (requestError) {
      setError(getApiError(requestError))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadMaterials()
  }, [])

  async function handleUpload(event) {
    event.preventDefault()

    if (!selectedFile) return

    setUploading(true)
    setError('')
    setNotice('')

    try {
      const uploaded = await api.uploadMaterial(selectedFile)

      setNotice(
        `${uploaded.filename} was processed and added to your course library.`
      )

      setSelectedFile(null)

      if (inputRef.current) {
        inputRef.current.value = ''
      }

      await loadMaterials()
    } catch (requestError) {
      setError(getApiError(requestError))
    } finally {
      setUploading(false)
    }
  }

  function chooseFile(event) {
    setNotice('')

    const file = event.target.files?.[0] || null

    if (
      file &&
      !['.pdf', '.pptx', '.mp4'].includes(
        file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
      )
    ) {
      setError('Choose a PDF, PPTX, or MP4 file.')
      setSelectedFile(null)
      event.target.value = ''
      return
    }

    setError('')
    setSelectedFile(file)
  }

  return (
    <div className="page-stack">
      {error && (
        <div className="error-banner">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {notice && <div className="success-banner">{notice}</div>}

      <section className="panel panel-pad">
        <div className="section-heading">
          <div>
            <h2>Add a course source</h2>
            <p>
              Files are extracted and indexed by the NovaMind backend.
            </p>
          </div>
        </div>

        <form onSubmit={handleUpload}>
          <input
            ref={inputRef}
            className="upload-input"
            type="file"
            accept=".pdf,.pptx,.mp4"
            onChange={chooseFile}
          />

          <div
            className="upload-zone"
            role="button"
            tabIndex={0}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                inputRef.current?.click()
              }
            }}
          >
            <div className="upload-icon">
              <FileUp size={20} />
            </div>

            <div className="upload-title">
              {selectedFile
                ? selectedFile.name
                : 'Choose a file to upload'}
            </div>

            <div className="upload-help">
              PDF, PPTX, or MP4 — the backend validates and processes the
              source.
            </div>

            <span className="button button-secondary">
              Browse files
            </span>
          </div>

          {selectedFile && (
            <div className="upload-submit-centered">
              <span className="muted small">
                Ready to send —{' '}
                {(selectedFile.size / (1024 * 1024)).toFixed(1)} MB
              </span>

              <button
                className="button button-primary"
                disabled={uploading}
                type="submit"
              >
                {uploading ? (
                  <>
                    <span className="spinner">⟳</span>
                    Processing…
                  </>
                ) : (
                  <>
                    <FileUp size={15} />
                    Upload source
                  </>
                )}
              </button>
            </div>
          )}
        </form>
      </section>

      <section>
        <div className="section-heading">
          <div>
            <h2>Course library</h2>
            <p>
              {loading
                ? 'Loading sources…'
                : `${materials.length} ${
                    materials.length === 1 ? 'source' : 'sources'
                  } in your library`}
            </p>
          </div>

          <button
            className="button button-secondary"
            onClick={loadMaterials}
            disabled={loading}
            type="button"
          >
            <RotateCw
              size={14}
              className={loading ? 'spinner' : ''}
            />
            Refresh
          </button>
        </div>

        <div className="panel panel-pad">
          {loading ? (
            <div className="loading-line">
              <span className="spinner">⟳</span>
              Loading course materials…
            </div>
          ) : materials.length > 0 ? (
            <>
              <div className="table-head">
                <span>Source</span>
                <span>Format</span>
                <span>Uploaded</span>
              </div>

              {materials.map((material) => (
                <div className="table-row" key={material.id}>
                  <div className="file-name-cell">
                    <div className="file-icon">
                      <MaterialIcon type={material.file_type} />
                    </div>

                    <div style={{ minWidth: 0 }}>
                      <div
                        className="file-name"
                        title={material.filename}
                      >
                        {material.filename}
                      </div>

                      <div className="file-meta">
                        Source ID {material.id}
                      </div>
                    </div>
                  </div>

                  <span>
                    <span className="format-tag">
                      {material.file_type}
                    </span>
                  </span>

                  <span className="muted small">
                    {formatDate(material.upload_date)}
                  </span>
                </div>
              ))}
            </>
          ) : (
            <EmptyState
              icon={FileText}
              title="Your course library is empty"
              description="Upload a source to make its pages or slides available to the assistant and assessments."
            />
          )}
        </div>
      </section>

      <div className="notice-inline">
        <Check size={14} />
        Sources are grounded to extracted page, slide, or transcript
        locations when available. MP4 processing depends on optional
        backend transcription support.
      </div>
    </div>
  )
}
