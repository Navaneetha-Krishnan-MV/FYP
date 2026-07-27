import React, { useState } from 'react';
import { X, Bug, FileSpreadsheet, Plus } from 'lucide-react';
import { createBugReport, uploadBugsCsv } from '../services/api';

interface AddBugModalProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const AddBugModal: React.FC<AddBugModalProps> = ({ projectId, isOpen, onClose, onSuccess }) => {
  const [tab, setTab] = useState<'single' | 'csv'>('single');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [severity, setSeverity] = useState('MEDIUM');
  const [externalBugId, setExternalBugId] = useState('');
  const [reporter, setReporter] = useState('');
  const [stepsToReproduce, setStepsToReproduce] = useState('');
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (tab === 'single') {
        if (!title || !description) throw new Error('Title and description are required');
        await createBugReport({
          projectId,
          title,
          description,
          severity,
          externalBugId: externalBugId || undefined,
          reporter: reporter || undefined,
          stepsToReproduce: stepsToReproduce || undefined,
        });
      } else {
        if (!csvFile) throw new Error('CSV file is required');
        await uploadBugsCsv(projectId, csvFile);
      }
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit bug report');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div className="glass-panel w-full max-w-lg rounded-2xl p-6 border border-rose-500/30 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/30">
            <Bug className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">File Bug Report</h2>
            <p className="text-xs text-slate-400">Add bug reports for AGTR localization and AI root cause analysis</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-2 p-1 bg-slate-950/60 rounded-xl border border-slate-800/80 mb-5">
          <button
            type="button"
            onClick={() => setTab('single')}
            className={`flex-1 py-2 px-4 rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 ${
              tab === 'single'
                ? 'bg-rose-600 text-white shadow-lg shadow-rose-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Plus className="w-4 h-4" />
            Single Bug
          </button>
          <button
            type="button"
            onClick={() => setTab('csv')}
            className={`flex-1 py-2 px-4 rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 ${
              tab === 'csv'
                ? 'bg-rose-600 text-white shadow-lg shadow-rose-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            Batch CSV Upload
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-semibold">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {tab === 'single' ? (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">External Bug ID</label>
                  <input
                    type="text"
                    placeholder="e.g. BUG-104"
                    value={externalBugId}
                    onChange={(e) => setExternalBugId(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950/70 border border-slate-800 text-white text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Severity</label>
                  <select
                    value={severity}
                    onChange={(e) => setSeverity(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950/70 border border-slate-800 text-white text-xs"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Bug Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Session invalidation failing when logging out user"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-white text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Description & Expected Behavior</label>
                <textarea
                  rows={3}
                  required
                  placeholder="Describe the issue, error messages, and observed vs expected behavior..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-white text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Steps to Reproduce (Optional)
                </label>
                <textarea
                  rows={3}
                  placeholder={'1. Sign in as a standard user\n2. Click "Log out"\n3. Reuse the old session cookie'}
                  value={stepsToReproduce}
                  onChange={(e) => setStepsToReproduce(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-white text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Reporter (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. QA Team"
                  value={reporter}
                  onChange={(e) => setReporter(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-white text-sm"
                />
              </div>
            </>
          ) : (
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">CSV File (`bug_id, title, description, severity, reporter`)</label>
              <div className="border-2 border-dashed border-slate-800 hover:border-rose-500/50 rounded-xl p-6 text-center bg-slate-950/40 transition cursor-pointer">
                <input
                  type="file"
                  accept=".csv"
                  required
                  onChange={(e) => setCsvFile(e.target.files ? e.target.files[0] : null)}
                  className="hidden"
                  id="csv-upload"
                />
                <label htmlFor="csv-upload" className="cursor-pointer flex flex-col items-center gap-2">
                  <FileSpreadsheet className="w-8 h-8 text-rose-400" />
                  <span className="text-xs font-semibold text-slate-200">
                    {csvFile ? csvFile.name : 'Click to select bug reports CSV'}
                  </span>
                  <span className="text-[10px] text-slate-500">Headers: bug_id, title, description, severity, reporter</span>
                </label>
              </div>
            </div>
          )}

          <div className="pt-2 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-600/30 transition disabled:opacity-50"
            >
              {loading ? 'Submitting...' : 'Submit Bug Report'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
