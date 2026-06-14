import React from "react";
import { X, FileText, Image as ImageIcon, Trash2 } from "lucide-react";
import FileUploader from "../FileUploader";

/**
 * Inline file-input that triggers a hidden picker. Used for avatar/banner.
 */
export function HiddenFileButton({ onUpload, accept = "image/jpeg,image/png,image/webp", testid, children, className = "" }) {
  const ref = React.useRef();
  return (
    <>
      <input ref={ref} type="file" accept={accept} className="hidden" data-testid={`${testid}-input`}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); e.target.value = ""; }} />
      <button onClick={() => ref.current?.click()} className={className} data-testid={`${testid}-btn`}>
        {children}
      </button>
    </>
  );
}

/** Company photo gallery — visible to everyone, manageable by the owner. */
export function ProfileGallery({ photos, isOwn, onAdd, onRemove }) {
  return (
    <div className="card-soft p-6" data-testid="gallery-section">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-bold flex items-center gap-2"><ImageIcon className="w-4 h-4" />Galerie photos</h2>
        {isOwn && <FileUploader kind="photo" accept="image/*" onUploaded={onAdd} label="Ajouter une photo" testid="upload-photo" />}
      </div>
      {photos.length === 0 ? (
        <p className="text-sm text-slate-400">Aucune photo dans la galerie</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {photos.map(ph => (
            <div key={ph.photo_id} className="relative aspect-square rounded-xl overflow-hidden bg-slate-100 group" data-testid={`photo-${ph.photo_id}`}>
              <img src={ph.url} alt={ph.title} className="w-full h-full object-cover" />
              {isOwn && (
                <button onClick={() => onRemove(ph.photo_id)} className="absolute top-2 right-2 bg-white/90 rounded-full p-1.5 opacity-0 group-hover:opacity-100 transition" data-testid={`remove-photo-${ph.photo_id}`}>
                  <X className="w-3.5 h-3.5 text-rose-600" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Candidate documents list (CV, cover letter…). */
export function ProfileDocuments({ docs, isOwn, onAdd, onDelete }) {
  return (
    <div className="card-soft p-6" data-testid="documents-section">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-bold flex items-center gap-2"><FileText className="w-4 h-4" />Documents</h2>
        {isOwn && <FileUploader kind="doc" accept=".pdf,.png,.jpg,.jpeg" onUploaded={onAdd} label="Ajouter un document" testid="upload-doc" />}
      </div>
      {docs.length === 0 ? (
        <p className="text-sm text-slate-400">Aucun document partagé</p>
      ) : (
        <div className="space-y-2">
          {docs.map(d => (
            <div key={d.doc_id} className="flex items-center justify-between bg-slate-50 rounded-xl p-3" data-testid={`doc-${d.doc_id}`}>
              <a href={`/api/files/${d.file_id}`} target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 flex-1 min-w-0 hover:text-blue-600">
                <FileText className="w-5 h-5 text-blue-500 shrink-0" />
                <div className="min-w-0">
                  <div className="font-semibold text-slate-900 text-sm truncate">{d.filename}</div>
                  <div className="text-xs text-slate-400">{d.doc_type} · {d.visibility}</div>
                </div>
              </a>
              {isOwn && <button onClick={() => onDelete(d.doc_id)} className="p-1.5 hover:bg-rose-50 rounded-full" data-testid={`del-doc-${d.doc_id}`}><Trash2 className="w-4 h-4 text-rose-500" /></button>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
