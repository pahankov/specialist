import React from 'react'
import './SharedComponents.css'

interface FilterOption {
  value: string
  label: string
}

interface FilterBarProps {
  options: FilterOption[]
  active: string
  onChange: (value: string) => void
}

export default function FilterBar({ options, active, onChange }: FilterBarProps) {
  return (
    <div className="filter-bar">
      {options.map((option) => (
        <button
          key={option.value}
          className={`filter-btn ${active === option.value ? 'active' : ''}`}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
