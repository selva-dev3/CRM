'use client';

import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check } from 'lucide-react';

export interface CustomSelectOption {
  value: string;
  label: string;
}

export interface CustomSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: CustomSelectOption[];
  placeholder?: string;
  className?: string;
  id?: string;
  color?: 'blue' | 'indigo' | 'purple' | 'amber';
}

export function CustomSelect({
  value,
  onChange,
  options,
  placeholder = 'Select an option',
  className = '',
  id,
  color = 'indigo',
}: CustomSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const selectedOption = options.find((opt) => opt.value === value);

  const activeColorClasses = {
    blue: {
      ring: 'focus:ring-blue-500/20 focus:border-blue-500',
      activeItem: 'bg-blue-50 text-blue-700 font-semibold',
      checkIcon: 'text-blue-600',
      arrowActive: 'text-blue-600',
    },
    indigo: {
      ring: 'focus:ring-indigo-500/20 focus:border-indigo-500',
      activeItem: 'bg-indigo-50 text-indigo-700 font-semibold',
      checkIcon: 'text-indigo-600',
      arrowActive: 'text-indigo-600',
    },
    purple: {
      ring: 'focus:ring-purple-500/20 focus:border-purple-500',
      activeItem: 'bg-purple-50 text-purple-700 font-semibold',
      checkIcon: 'text-purple-600',
      arrowActive: 'text-purple-600',
    },
    amber: {
      ring: 'focus:ring-amber-500/20 focus:border-amber-500',
      activeItem: 'bg-amber-50 text-amber-700 font-semibold',
      checkIcon: 'text-amber-600',
      arrowActive: 'text-amber-600',
    },
  }[color];

  return (
    <div ref={dropdownRef} className={`relative w-full ${className}`}>
      <button
        id={id}
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={`w-full h-9 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-900 flex items-center justify-between shadow-xs hover:border-slate-400 focus:outline-none focus:ring-2 ${activeColorClasses.ring} transition cursor-pointer`}
      >
        <span className="truncate">{selectedOption ? selectedOption.label : placeholder}</span>
        <ChevronDown
          className={`w-4 h-4 text-slate-400 shrink-0 transition-transform duration-200 ${
            isOpen ? `rotate-180 ${activeColorClasses.arrowActive}` : ''
          }`}
        />
      </button>

      {isOpen && (
        <div className="absolute left-0 right-0 top-full mt-1 z-50 bg-white border border-slate-200 rounded-xl shadow-xl py-1 max-h-48 overflow-y-auto animate-in fade-in-50 zoom-in-95">
          {options.map((option) => {
            const isSelected = option.value === value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setIsOpen(false);
                }}
                className={`w-[calc(100%-8px)] mx-1 px-2.5 py-2 text-xs font-medium rounded-lg flex items-center justify-between cursor-pointer transition text-left ${
                  isSelected
                    ? activeColorClasses.activeItem
                    : 'text-slate-700 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                <span className="truncate">{option.label}</span>
                {isSelected && <Check className={`w-3.5 h-3.5 ${activeColorClasses.checkIcon} shrink-0`} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
