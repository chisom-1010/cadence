/** A small airmail envelope: the brand mark. */
export default function Mark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size * 0.72} viewBox="0 0 36 26" aria-hidden="true">
      <defs>
        <pattern id="dv-stripe" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
          <rect width="4" height="8" fill="var(--air)" />
          <rect x="4" width="4" height="8" fill="var(--signal)" />
        </pattern>
      </defs>
      <rect x="1" y="1" width="34" height="24" rx="3" fill="var(--paper)" stroke="url(#dv-stripe)" strokeWidth="2.4" />
      <path d="M4 6l14 10L32 6" fill="none" stroke="var(--ink)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
