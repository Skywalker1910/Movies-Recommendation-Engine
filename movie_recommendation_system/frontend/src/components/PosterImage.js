import React, { useEffect, useState } from 'react';

/**
 * Renders a remote poster and replaces it with caller-provided content when
 * the URL is missing or the image host returns an error.
 */
export default function PosterImage({
  src,
  alt,
  className,
  fallback,
  loading = 'lazy',
}) {
  const [failed, setFailed] = useState(false);

  // A component can be reused for a different movie in a changing result row.
  useEffect(() => setFailed(false), [src]);

  if (!src || failed) return fallback;

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      loading={loading}
      decoding="async"
      onError={() => setFailed(true)}
    />
  );
}

