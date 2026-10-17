interface VkIconProps {
  size?: number;
}

/** VK brand mark: blue rounded square with a white «VK» glyph. */
function VkIcon({ size = 20 }: VkIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="2" y="2" width="20" height="20" rx="6" fill="#0077FF" />
      {/* White «VK» wordmark, centered. */}
      <path
        d="M12.8 16.4h1.05c.36 0 .5-.16.63-.53.24-.66.8-2.05 1.6-2.9.06-.06.13-.03.13.03v1.36c0 .26.01.4-.14.55-.15.15-.36.24-.6.24h-.87c-.4 0-.6-.2-.84-.63-.18-.33-.35-.66-.54-.98-.07-.12-.14-.18-.28-.18h-.47c-.2 0-.3.06-.3.3 0 .33.47.64.82 1.1.45.58.64 1.06.7 1.7.02.13-.04.22-.17.22Zm-3.05-3.86h1.34c.1 0 .16.06.16.17v4.68c0 .2-.08.28-.25.28h-.84c-.16 0-.24-.08-.24-.28v-3.4c0-.2-.03-.43-.16-.6a.56.56 0 0 0-.46-.2h-.6c-.13 0-.2.07-.2.2 0 .3.44.55.72.96l1.5 2.04Z"
        fill="#fff"
      />
      <path
        d="M7.6 12.34c0-.17.08-.26.24-.26h.9c.13 0 .2.07.2.22 0 .33.3.7.55 1 .2.22.3.47.3.73 0 .5-.3.82-.8.82h-.72c-.16 0-.24-.07-.32-.22l-.86-1.5c-.06-.1-.1-.16-.1-.23Z"
        fill="#fff"
      />
    </svg>
  );
}

export default VkIcon;
