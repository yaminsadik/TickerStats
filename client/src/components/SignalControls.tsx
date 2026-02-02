import type { SignalSettings } from '../types/signals';

interface SignalControlsProps {
  settings: SignalSettings;
  onToggle: () => void;
  onModeChange: (mode: 'percentile' | 'absolute') => void;
  onConfigure: () => void;
}

export default function SignalControls({
  settings,
  onToggle,
  onModeChange,
  onConfigure,
}: SignalControlsProps) {
  return (
    <div className="flex items-center gap-4">
      {/* Enable/Disable Toggle */}
      <label className="flex items-center gap-2 cursor-pointer select-none">
        <div className="relative">
          <input
            type="checkbox"
            checked={settings.enabled}
            onChange={onToggle}
            className="sr-only peer"
          />
          <div className="w-9 h-5 bg-slate-300 rounded-full peer-checked:bg-emerald-500 transition-colors" />
          <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow peer-checked:translate-x-4 transition-transform" />
        </div>
        <span className="text-sm font-medium text-slate-700">Signals</span>
      </label>

      {/* Mode Selector (only visible when enabled) */}
      {settings.enabled && (
        <>
          <div className="h-5 w-px bg-slate-300" />
          
          <div className="flex items-center gap-1 bg-slate-100 rounded-md p-0.5">
            <button
              onClick={() => onModeChange('percentile')}
              className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                settings.globalMode === 'percentile'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Percentile
            </button>
            <button
              onClick={() => onModeChange('absolute')}
              className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                settings.globalMode === 'absolute'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Absolute
            </button>
          </div>

          <button
            onClick={onConfigure}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded transition-colors"
          >
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            Configure
          </button>
        </>
      )}
    </div>
  );
}
