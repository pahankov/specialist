interface YandexIconProps {
  size?: number;
}

/**
 * Yandex brand mark: red rounded square with a white «Я» glyph.
 * The glyph is built from four subpaths (stem, bowl, bowl counter, leg)
 * combined with fill-rule="evenodd" so the counter reads as a hole.
 */
function YandexIcon({ size = 20 }: YandexIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="2" y="2" width="20" height="20" rx="6" fill="#FC3F1D" />
      {/* White «Я» wordmark, centered. */}
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="
          M14.6 5.8 H17.2 V18.2 H14.6 Z
          M14.6 5.8 H10.2 A3.3 3.3 0 0 0 10.2 12.4 H14.6 Z
          M14.6 7.9 H11.8 A1.2 1.2 0 0 0 11.8 10.3 H14.6 Z
          M11.0 12.4 H13.8 L8.8 18.2 H6.2 Z
        "
        fill="#fff"
      />
    </svg>
  );
}

export default YandexIcon;
