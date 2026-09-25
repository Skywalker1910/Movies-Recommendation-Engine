import React from 'react';

export default function SkeletonCard() {
  return (
    <div className="card" style={{ cursor: 'default', pointerEvents: 'none' }}>
      <div className="skeleton card-sk-poster" />
      <div className="card-body">
        <div className="skeleton card-sk-title" />
        <div className="skeleton card-sk-meta" style={{ marginTop: 6 }} />
      </div>
    </div>
  );
}

export function SkeletonRow({ count = 6 }) {
  return (
    <div className="scroll-row">
      {Array.from({ length: count }).map((_, i) => <SkeletonCard key={i} />)}
    </div>
  );
}
