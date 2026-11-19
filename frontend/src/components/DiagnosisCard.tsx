import React, { useState } from 'react';
import { 
  AlertTriangle, CheckCircle2, XCircle, Copy, ChevronDown, ChevronUp,
  RefreshCw, Zap, Eye, ThumbsUp, ThumbsDown, Terminal, Info, Clock, Check
} from 'lucide-react';
import { DiagnosisCard as DiagnosisCardType, submitFeedback } from '../lib/api';
import { categoryColors, confidenceColor, cn } from '../lib/utils';

interface Props {
  diagnosis: DiagnosisCardType;
  onFeedbackSubmitted?: () => void;
}

export default function DiagnosisCardComponent({ diagnosis, onFeedbackSubmitted }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [copied, setCopied] = useState(false);
  const [feedbackSent, setFeedbackSent] = useState(diagnosis.resolution_status !== 'PENDING');
  const [feedbackStatus, setFeedbackStatus] = useState(diagnosis.resolution_status);

  const handleCopy = () => {
    if (diagnosis.recommended_fix) {
      navigator.clipboard.writeText(diagnosis.recommended_fix);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleFeedback = async (worked: boolean) => {
    try {
      await submitFeedback(diagnosis.id, worked);
      setFeedbackSent(true);
      setFeedbackStatus(worked ? 'RESOLVED' : 'UNRESOLVED');
      onFeedbackSubmitted?.();
    } catch (e) {
      console.error('Feedback error:', e);
    }
  };

  return (
    <div className="bg-navy-900 border border-navy-700/70 rounded-xl overflow-hidden shadow-lg transition-all hover:border-navy-600">
      {/* Top Header */}
      <div className="p-4 sm:p-5 flex items-start gap-3.5 border-b border-navy-800">
        <div className="mt-0.5 p-2 rounded-lg bg-navy-800 border border-navy-700">
          {diagnosis.is_flaky ? (
            <Zap className="w-5 h-5 text-amber-400" />
          ) : (
            <AlertTriangle className="w-5 h-5 text-rose-400" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={cn('text-xs font-semibold px-2.5 py-0.5 rounded-full border', categoryColors[diagnosis.failure_category] || categoryColors.UNKNOWN)}>
              {diagnosis.failure_category.replace('_', ' ')}
            </span>
            {diagnosis.is_flaky && (
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full border text-amber-400 bg-amber-950/40 border-amber-800/50 flex items-center gap-1">
                <Zap className="w-3 h-3" /> FLAKY TEST
              </span>
            )}
            {diagnosis.rerun_recommended && (
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full border text-cyan-400 bg-cyan-950/40 border-cyan-800/50 flex items-center gap-1">
                <RefreshCw className="w-3 h-3" /> RERUN RECOMMENDED
              </span>
            )}
            <div className="ml-auto flex items-center gap-1.5">
              <span className="text-xs text-slate-500 font-medium">Confidence:</span>
              <span className={cn('text-xs font-mono font-bold', confidenceColor(diagnosis.confidence_score))}>
                {Math.round(diagnosis.confidence_score * 100)}%
              </span>
            </div>
          </div>

          {diagnosis.failed_step && (
            <p className="text-slate-300 text-xs font-medium mt-1">
              Failed Step: <span className="font-mono text-blue-400 bg-navy-800/80 px-1.5 py-0.5 rounded border border-navy-700/60">{diagnosis.failed_step}</span>
            </p>
          )}

          <p className="text-rose-300 font-mono text-xs sm:text-sm mt-2 break-all bg-rose-950/20 p-2.5 rounded-lg border border-rose-900/30">
            {diagnosis.error_message || 'Unspecified failure message'}
          </p>
        </div>
      </div>

      {/* Root Cause & Reasoning */}
      <div className="p-4 sm:p-5 space-y-4">
        {diagnosis.root_cause && (
          <div className="bg-navy-950/60 rounded-lg p-3.5 border border-navy-800/80">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 mb-1">
              <Info className="w-3.5 h-3.5 text-blue-400" />
              <span>LIKELY ROOT CAUSE</span>
            </div>
            <p className="text-slate-200 text-sm leading-relaxed">{diagnosis.root_cause}</p>
          </div>
        )}

        {/* Recommended Fix */}
        {diagnosis.recommended_fix && (
          <div className="bg-emerald-950/20 rounded-lg p-4 border border-emerald-800/40">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>RECOMMENDED RESOLUTION</span>
              </div>
              <button
                onClick={handleCopy}
                className="text-xs text-slate-400 hover:text-emerald-400 flex items-center gap-1 transition-colors bg-navy-900/80 px-2 py-1 rounded border border-navy-700"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copied ? 'Copied' : 'Copy Fix'}</span>
              </button>
            </div>
            <p className="text-slate-200 text-sm leading-relaxed">{diagnosis.recommended_fix}</p>

            {/* Suggested Commands */}
            {diagnosis.commands && diagnosis.commands.length > 0 && (
              <div className="mt-3 space-y-1.5">
                <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Suggested Shell Commands:</p>
                {diagnosis.commands.map((cmd, i) => (
                  <div key={i} className="flex items-center gap-2 bg-navy-950/80 rounded px-2.5 py-1.5 border border-navy-800">
                    <Terminal className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                    <code className="text-xs font-mono text-emerald-300 break-all select-all">{cmd}</code>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Historical Matches from Vector Memory */}
        {diagnosis.similar_failures && diagnosis.similar_failures.length > 0 && (
          <div className="bg-navy-950/40 rounded-lg p-3.5 border border-navy-800">
            <p className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1.5">
              <span>ChromaDB Memory: {diagnosis.similar_failures.length} Similar Failure(s)</span>
            </p>
            <div className="space-y-2">
              {diagnosis.similar_failures.map((sf, i) => (
                <div key={i} className="bg-navy-900/80 rounded p-2.5 border border-navy-700/50 text-xs">
                  <div className="flex items-center justify-between text-slate-400 mb-1">
                    <span className="font-medium text-blue-400">{sf.category}</span>
                    <span className="font-mono text-[11px] text-slate-400">{Math.round(sf.similarity_score * 100)}% match</span>
                  </div>
                  <p className="text-slate-300 truncate font-mono text-[11px] mb-1">{sf.error_pattern}</p>
                  <p className="text-slate-400 text-[11px]"><strong className="text-slate-300">Solution:</strong> {sf.fix}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Expandable Reasoning and Evidence */}
        <div className="flex items-center gap-3 pt-1 text-xs">
          {diagnosis.reasoning && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-slate-400 hover:text-slate-200 flex items-center gap-1 transition-colors"
            >
              {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              <span>{expanded ? 'Hide Reasoning' : 'View Agent Reasoning'}</span>
            </button>
          )}

          {diagnosis.log_evidence && (
            <button
              onClick={() => setShowEvidence(!showEvidence)}
              className="text-slate-400 hover:text-slate-200 flex items-center gap-1 transition-colors ml-auto"
            >
              <Eye className="w-3.5 h-3.5" />
              <span>{showEvidence ? 'Hide Evidence' : 'View Log Snippet'}</span>
            </button>
          )}
        </div>

        {expanded && diagnosis.reasoning && (
          <div className="bg-navy-950 p-3 rounded-lg border border-navy-800 text-xs text-slate-300 leading-relaxed font-sans">
            <strong className="text-blue-400 block mb-1">Diagnosis Analysis:</strong>
            {diagnosis.reasoning}
          </div>
        )}

        {showEvidence && diagnosis.log_evidence && (
          <div className="bg-navy-950 p-3 rounded-lg border border-navy-800">
            <div className="flex items-center justify-between mb-1.5 text-[11px] text-slate-500">
              <span>Extracted Log Context:</span>
            </div>
            <pre className="text-xs font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed">
              {diagnosis.log_evidence}
            </pre>
          </div>
        )}
      </div>

      {/* Developer Feedback Footer */}
      <div className="px-5 py-3 border-t border-navy-800 bg-navy-950/60 flex items-center justify-between">
        <span className="text-xs text-slate-400 font-medium">Was this diagnosis accurate?</span>
        {feedbackSent ? (
          <div className="flex items-center gap-2 text-xs">
            {feedbackStatus === 'RESOLVED' ? (
              <span className="text-emerald-400 font-medium flex items-center gap-1 bg-emerald-950/50 px-2.5 py-1 rounded-full border border-emerald-800/40">
                <CheckCircle2 className="w-3.5 h-3.5" /> Fix Confirmed
              </span>
            ) : (
              <span className="text-rose-400 font-medium flex items-center gap-1 bg-rose-950/50 px-2.5 py-1 rounded-full border border-rose-800/40">
                <XCircle className="w-3.5 h-3.5" /> Fix Ineffective
              </span>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleFeedback(true)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-emerald-950/40 text-emerald-400 border border-emerald-800/50 hover:bg-emerald-900/50 transition-colors font-medium"
            >
              <ThumbsUp className="w-3.5 h-3.5" /> Worked
            </button>
            <button
              onClick={() => handleFeedback(false)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-rose-950/40 text-rose-400 border border-rose-800/50 hover:bg-rose-900/50 transition-colors font-medium"
            >
              <ThumbsDown className="w-3.5 h-3.5" /> Didn't work
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
