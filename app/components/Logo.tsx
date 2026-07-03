export default function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" style={{ flexShrink: 0 }}>
      <circle cx="32" cy="32" r="27" fill="var(--t-surface)" stroke="var(--t-accent)" strokeWidth="2.5" />
      <polygon points="44.73,19.27 34.47,34.47 29.53,29.53" fill="var(--t-accent-dark)" />
      <polygon points="22.1,41.9 34.47,34.47 29.53,29.53" fill="var(--t-accent-border)" />
      <circle cx="32" cy="32" r="3" fill="var(--t-surface)" stroke="var(--t-accent)" strokeWidth="1.5" />
    </svg>
  );
}
