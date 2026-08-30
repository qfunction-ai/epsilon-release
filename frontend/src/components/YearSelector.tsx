import { useEffect, useRef, useState } from 'react';
import type { YearInfo } from '../types';

interface YearSelectorProps {
  years: YearInfo[];
  selectedYear: number;
  onSelectYear: (year: number) => void;
}

export function YearSelector({ years, selectedYear, onSelectYear }: YearSelectorProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentYearInfo = years.find((y) => y.year === selectedYear);

  function handleSelectYear(year: number) {
    onSelectYear(year);
    setOpen(false);
  }

  return (
    <div className="year-selector">
      <div className="year-selector-label">OWASP Edition</div>
      <div className="year-selector-wrap" ref={wrapRef}>
        <button
          type="button"
          className={`year-selector-dropdown${open ? ' open' : ''}`}
          onClick={() => setOpen(!open)}
        >
          <span className="year-selector-current">
            <span className="year-num">{selectedYear}</span>
            {currentYearInfo?.latest && <span className="year-tag">Latest</span>}
          </span>
          <span className="year-selector-arrow">▾</span>
        </button>
        <div className={`year-selector-menu${open ? ' open' : ''}`}>
          {years.map((yearInfo) => (
            <div
              key={yearInfo.year}
              className={`year-option${yearInfo.year === selectedYear ? ' selected' : ''}`}
              onClick={() => handleSelectYear(yearInfo.year)}
            >
              <span>
                <span style={{ fontWeight: 600 }}>{yearInfo.year}</span>
                {yearInfo.latest && <span className="year-tag">Latest</span>}
              </span>
              <span className="year-count">{yearInfo.entries.length} entries</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
