import { useState, useCallback, KeyboardEvent, ClipboardEvent } from 'react';

interface TickerInputProps {
  tickers: string[];
  onTickersChange: (tickers: string[]) => void;
  disabled?: boolean;
}

export function TickerInput({ tickers, onTickersChange, disabled }: TickerInputProps) {
  const [inputValue, setInputValue] = useState('');

  const parseTickers = useCallback((text: string): string[] => {
    // Support comma, space, tab, newline separated tickers
    return text
      .toUpperCase()
      .split(/[\s,\t\n]+/)
      .map((t) => t.trim())
      .filter((t) => t.length > 0 && /^[A-Z0-9.^-]+$/.test(t));
  }, []);

  const addTickers = useCallback(
    (newTickers: string[]) => {
      const uniqueNew = newTickers.filter((t) => !tickers.includes(t));
      if (uniqueNew.length > 0) {
        onTickersChange([...tickers, ...uniqueNew]);
      }
    },
    [tickers, onTickersChange]
  );

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',' || e.key === ' ' || e.key === 'Tab') {
      e.preventDefault();
      const parsed = parseTickers(inputValue);
      if (parsed.length > 0) {
        addTickers(parsed);
        setInputValue('');
      }
    } else if (e.key === 'Backspace' && inputValue === '' && tickers.length > 0) {
      onTickersChange(tickers.slice(0, -1));
    }
  };

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pastedText = e.clipboardData.getData('text');
    const parsed = parseTickers(pastedText);
    if (parsed.length > 0) {
      addTickers(parsed);
      setInputValue('');
    }
  };

  const handleBlur = () => {
    const parsed = parseTickers(inputValue);
    if (parsed.length > 0) {
      addTickers(parsed);
      setInputValue('');
    }
  };

  const removeTicker = (ticker: string) => {
    onTickersChange(tickers.filter((t) => t !== ticker));
  };

  return (
    <div className="w-full">
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        Tickers
      </label>
      <div
        className={`flex flex-wrap gap-1.5 p-2 bg-white border border-gray-300 rounded-lg focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500 min-h-[44px] ${
          disabled ? 'bg-gray-50 cursor-not-allowed' : ''
        }`}
      >
        {tickers.map((ticker) => (
          <span
            key={ticker}
            className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-800 text-sm font-medium rounded-md"
          >
            {ticker}
            {!disabled && (
              <button
                type="button"
                onClick={() => removeTicker(ticker)}
                className="text-blue-600 hover:text-blue-800 focus:outline-none"
                aria-label={`Remove ${ticker}`}
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
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            )}
          </span>
        ))}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value.toUpperCase())}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          onBlur={handleBlur}
          disabled={disabled}
          placeholder={tickers.length === 0 ? 'Type or paste tickers (e.g., AAPL MSFT NVDA)' : ''}
          className="flex-1 min-w-[150px] outline-none text-sm text-gray-900 placeholder:text-gray-400 bg-transparent disabled:cursor-not-allowed"
        />
      </div>
      <p className="mt-1 text-xs text-gray-500">
        Press Enter, Space, or Tab to add. Paste multiple tickers at once.
      </p>
    </div>
  );
}
