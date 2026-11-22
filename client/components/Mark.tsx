/** The Cadance mark: a sun-coloured disc with an open "C". */
export default function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id="cd-sun" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffb08f" />
          <stop offset="1" stopColor="#ff7a4d" />
        </linearGradient>
      </defs>
      <circle cx="16" cy="16" r="15" fill="url(#cd-sun)" />
      <path d="M21.5 11.2a7 7 0 1 0 0 9.6" fill="none" stroke="#2e0d02" strokeWidth="2.8" strokeLinecap="round" />
    </svg>
  );
}
