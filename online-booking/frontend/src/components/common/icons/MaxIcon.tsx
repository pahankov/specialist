interface MaxIconProps {
  size?: number;
}

/** MAX messenger mark: indigo rounded square with a white «M» glyph. */
function MaxIcon({ size = 20 }: MaxIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="2" y="2" width="20" height="20" rx="6" fill="url(#maxIconGradient)" />
      <path d="M7 16.5V7.5h2.6L12 12l2.4-4.5H17v9h-2.4v-5.6L12 15.4 9.4 10.9v5.6H7Z" fill="#fff" />
      <defs>
        <linearGradient
          id="maxIconGradient"
          x1="2"
          y1="2"
          x2="22"
          y2="22"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#5B6CFF" />
          <stop offset="1" stopColor="#3D4EDB" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export default MaxIcon;
