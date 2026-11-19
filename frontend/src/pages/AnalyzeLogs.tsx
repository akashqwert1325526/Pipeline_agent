import React, { useState, useRef, useCallback } from 'react';
import { 
  Upload, FileText, X, Loader2, AlertCircle, ArrowRight, 
  Terminal, Sparkles, CheckCircle2, RefreshCw
} from 'lucide-react';
import { analyzeFile, analyzeText, AnalysisResponse } from '../lib/api';
import DiagnosisCardComponent from '../components/DiagnosisCard';
import { cn } from '../lib/utils';

export default function AnalyzeLogs() {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState('');
  const [preview, setPreview] = useState('');
  const [mode, setMode] = useState<'file' | 'text'>('file');
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    if (!f.name.match(/\.(txt|log)$/i)) {
      setError('Only .txt and .log file formats are supported.');
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      setError('File exceeds the 10 MB maximum upload limit.');
      return;
    }
    setError('');
    setFile(f);
    const reader = new FileReader();
    reader.onload = (e) => {
      setPreview(((e.target?.result as string) || '').slice(0, 3000));
    };
    reader.readAsText(f);
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, []);

  const handleAnalyze = async () => {
    setError('');
    setResult(null);
    setLoading(true);
    try {
      const res = mode === 'file' && file
        ? await analyzeFile(file)
        : await analyzeText(text, 'manual_input.log');
      setResult(res.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Log analysis failed.');
    } finally {
      setLoading(false);
    }
  };

  const loadSample = (sampleType: 'python' | 'npm' | 'docker') => {
    setMode('text');
    if (sampleType === 'python') {
      setText(`2024-01-15T10:23:01.1234567Z ##[group]Run actions/checkout@v4
2024-01-15T10:23:02.1234567Z ##[endgroup]
2024-01-15T10:23:05.1234567Z ##[group]Run tests
2024-01-15T10:23:10.1234567Z collected 12 items
2024-01-15T10:23:12.1234567Z tests/test_services.py::test_payment_service FAILED [ 33%]
2024-01-15T10:23:12.1234567Z =================================== FAILURES ===================================
2024-01-15T10:23:12.1234567Z _________________________ test_payment_service _________________________
2024-01-15T10:23:12.1234567Z     def test_payment_service():
2024-01-15T10:23:12.1234567Z >       processor = PaymentProcessor(api_key=os.environ['STRIPE_API_KEY'])
2024-01-15T10:23:12.1234567Z E       KeyError: 'STRIPE_API_KEY'
2024-01-15T10:23:12.1234567Z tests/test_services.py:45: KeyError
2024-01-15T10:23:12.1234567Z _________________________ test_email_sender _________________________
2024-01-15T10:23:12.1234567Z >       import sendgrid
2024-01-15T10:23:12.1234567Z E       ModuleNotFoundError: No module named 'sendgrid'
2024-01-15T10:23:12.1234567Z tests/test_services.py:52: ModuleNotFoundError
2024-01-15T10:23:12.1234567Z ##[endgroup]
2024-01-15T10:23:12.1234567Z ::error::Process completed with exit code 1.`);
    } else if (sampleType === 'npm') {
      setText(`npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /app/package.json
npm ERR! errno -2
npm ERR! enoent ENOENT: no such file or directory, open '/app/package.json'
npm ERR! enoent This is related to npm not being able to find a file.
npm ERR! A complete log of this run can be found in: /root/.npm/_logs/2024-01-15T11_00_00_000Z-debug-0.log`);
    } else {
      setText(`Step 4/10 : RUN pip install -r requirements.txt
 ---> Running in a1b2c3d4e5f6
failed to solve: failed to compute cache key: "/requirements.txt" not found: not found
docker: Error response from daemon: dockerfile parse error on line 4: unknown instruction: UNKNOWN_CMD`);
    }
  };

  const canAnalyze = mode === 'file' ? !!file : text.trim().length > 10;

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-navy-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Investigate CI/CD Failures</h1>
          <p className="text-slate-400 text-sm mt-1">Upload pipeline log files or paste raw console output for diagnosis</p>
        </div>

        {/* Preset sample buttons */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-medium">Try Sample:</span>
          <button
            onClick={() => loadSample('python')}
            className="px-2.5 py-1 text-xs bg-navy-800 hover:bg-navy-700 text-slate-300 rounded-md border border-navy-700 transition-colors"
          >
            Python
          </button>
          <button
            onClick={() => loadSample('npm')}
            className="px-2.5 py-1 text-xs bg-navy-800 hover:bg-navy-700 text-slate-300 rounded-md border border-navy-700 transition-colors"
          >
            Node.js
          </button>
          <button
            onClick={() => loadSample('docker')}
            className="px-2.5 py-1 text-xs bg-navy-800 hover:bg-navy-700 text-slate-300 rounded-md border border-navy-700 transition-colors"
          >
            Docker
          </button>
        </div>
      </div>

      {/* Input Mode Selector */}
      <div className="flex items-center gap-1 p-1 bg-navy-900 border border-navy-800 rounded-lg w-fit">
        <button
          onClick={() => { setMode('file'); setError(''); }}
          className={cn(
            'px-4 py-1.5 rounded-md text-xs font-semibold transition-all flex items-center gap-2',
            mode === 'file' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
          )}
        >
          <Upload className="w-3.5 h-3.5" />
          <span>Upload Log File</span>
        </button>
        <button
          onClick={() => { setMode('text'); setError(''); }}
          className={cn(
            'px-4 py-1.5 rounded-md text-xs font-semibold transition-all flex items-center gap-2',
            mode === 'text' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
          )}
        >
          <Terminal className="w-3.5 h-3.5" />
          <span>Paste Log Output</span>
        </button>
      </div>

      {/* Upload Zone / Text Area */}
      {mode === 'file' ? (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
          className={cn(
            'border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-3',
            dragging 
              ? 'border-blue-500 bg-blue-950/20' 
              : 'border-navy-700/80 bg-navy-900/60 hover:border-blue-500/50 hover:bg-navy-900'
          )}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.log"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />

          {file ? (
            <div className="flex items-center gap-4 bg-navy-800/80 p-4 rounded-xl border border-navy-700">
              <FileText className="w-10 h-10 text-blue-400" />
              <div className="text-left">
                <p className="text-white font-medium text-sm">{file.name}</p>
                <p className="text-slate-400 text-xs">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                  setPreview('');
                }}
                className="p-1.5 text-slate-400 hover:text-rose-400 transition-colors ml-4"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          ) : (
            <>
              <div className="w-12 h-12 rounded-full bg-navy-800 border border-navy-700 flex items-center justify-center text-blue-400 mb-1">
                <Upload className="w-6 h-6" />
              </div>
              <div>
                <p className="text-slate-200 font-medium text-sm">Drag and drop log file here, or click to browse</p>
                <p className="text-slate-500 text-xs mt-1">Accepts raw .txt or .log files up to 10 MB</p>
              </div>
            </>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Raw CI/CD Output:</span>
            <span className="font-mono text-[11px]">{text.length} characters</span>
          </div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste raw terminal logs, build traces, or test outputs here..."
            className="w-full h-72 bg-navy-900 border border-navy-700/80 rounded-xl p-4 text-xs font-mono text-slate-200 resize-none outline-none focus:border-blue-500 transition-all placeholder:text-slate-600 leading-relaxed"
          />
        </div>
      )}

      {/* Log Preview */}
      {preview && mode === 'file' && (
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Log Preview (first 3000 chars):</span>
          </div>
          <pre className="text-xs font-mono text-slate-400 bg-navy-950 p-3 rounded-lg overflow-x-auto max-h-40 overflow-y-auto whitespace-pre-wrap border border-navy-800">
            {preview}
          </pre>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="flex items-center gap-2.5 p-4 bg-rose-950/40 border border-rose-800/50 rounded-xl text-rose-300 text-sm">
          <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Action CTA */}
      <button
        onClick={handleAnalyze}
        disabled={!canAnalyze || loading}
        className="w-full py-3.5 bg-blue-600 hover:bg-blue-500 disabled:bg-navy-800 disabled:text-slate-500 text-white font-semibold rounded-xl text-sm transition-all shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Parsing logs & querying vector memory...</span>
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            <span>Run AI Diagnosis</span>
          </>
        )}
      </button>

      {/* Diagnosis Results Section */}
      {result && (
        <div className="pt-6 border-t border-navy-800 space-y-6">
          <div className="flex items-center justify-between bg-navy-900 border border-navy-800 p-4 rounded-xl">
            <div>
              <h2 className="text-lg font-bold text-white">Diagnosis Report</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Platform: <strong className="text-blue-400">{result.platform || 'generic'}</strong> • {result.failure_count} {result.failure_count === 1 ? 'failure' : 'failures'} isolated
              </p>
            </div>
            <span className={cn(
              'px-3 py-1 rounded-full text-xs font-semibold',
              result.failure_count > 0 ? 'bg-rose-950/60 text-rose-400 border border-rose-800/50' : 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50'
            )}>
              {result.failure_count > 0 ? 'Action Required' : 'Clean Build'}
            </span>
          </div>

          {result.diagnoses.length === 0 ? (
            <div className="text-center py-12 bg-navy-900/40 border border-navy-800 rounded-xl text-slate-400">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
              <p className="font-semibold text-white">No Failure Patterns Identified</p>
              <p className="text-xs text-slate-500 mt-1">The provided log output appears clean or contains no recognizable error signatures.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {result.diagnoses.map((diag) => (
                <DiagnosisCardComponent key={diag.id} diagnosis={diag} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
