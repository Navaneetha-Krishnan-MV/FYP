import React, { useState } from 'react';
import { X, GitBranch, UploadCloud, FileArchive, Sparkles } from 'lucide-react';
import { createProjectGithub, createProjectZip } from '../services/api';

interface AddProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const AddProjectModal: React.FC<AddProjectModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [tab, setTab] = useState<'github' | 'zip'>('github');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (tab === 'github') {
        if (!name || !repoUrl) {
          throw new Error('Project name and GitHub URL are required');
        }
        await createProjectGithub(name, description, repoUrl);
      } else {
        if (!name || !zipFile) {
          throw new Error('Project name and ZIP file are required');
        }
        await createProjectZip(name, description, zipFile);
      }
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div className="glass-panel w-full max-w-lg rounded-2xl p-6 border border-indigo-500/30 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
            <Sparkles className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Ingest New Repository</h2>
            <p className="text-xs text-slate-400">Trigger multi-language AST parsing, embedding & graph indexing</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-2 p-1 bg-slate-950/60 rounded-xl border border-slate-800/80 mb-5">
          <button
            type="button"
            onClick={() => setTab('github')}
            className={`flex-1 py-2 px-4 rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 ${
              tab === 'github'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <GitBranch className="w-4 h-4" />
            GitHub Repository
          </button>
          <button
            type="button"
            onClick={() => setTab('zip')}
            className={`flex-1 py-2 px-4 rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 ${
              tab === 'zip'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <FileArchive className="w-4 h-4" />
            Local ZIP Upload
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-semibold">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">Project Name</label>
            <input
              type="text"
              required
              placeholder="e.g. CodeLens Backend"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-white text-sm focus:outline-none focus:border-indigo-500 transition"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">Description (Optional)</label>
            <input
              type="text"
              placeholder="Brief description of project domain"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-white text-sm focus:outline-none focus:border-indigo-500 transition"
            />
          </div>

          {tab === 'github' ? (
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">GitHub Repository URL</label>
              <input
                type="url"
                required
                placeholder="https://github.com/org/repo.git"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-white text-sm focus:outline-none focus:border-indigo-500 transition"
              />
            </div>
          ) : (
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Repository ZIP Archive</label>
              <div className="border-2 border-dashed border-slate-800 hover:border-indigo-500/50 rounded-xl p-6 text-center bg-slate-950/40 transition cursor-pointer">
                <input
                  type="file"
                  accept=".zip"
                  required
                  onChange={(e) => setZipFile(e.target.files ? e.target.files[0] : null)}
                  className="hidden"
                  id="zip-upload"
                />
                <label htmlFor="zip-upload" className="cursor-pointer flex flex-col items-center gap-2">
                  <UploadCloud className="w-8 h-8 text-indigo-400" />
                  <span className="text-xs font-semibold text-slate-200">
                    {zipFile ? zipFile.name : 'Click to upload source code ZIP'}
                  </span>
                  <span className="text-[10px] text-slate-500">Supports Python, JavaScript, TypeScript, Java</span>
                </label>
              </div>
            </div>
          )}

          <div className="pt-2 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold shadow-lg shadow-indigo-600/30 transition disabled:opacity-50"
            >
              {loading ? 'Ingesting Pipeline...' : 'Start Indexing Pipeline'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
