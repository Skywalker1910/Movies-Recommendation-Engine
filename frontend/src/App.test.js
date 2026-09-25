import { fireEvent, render, screen } from '@testing-library/react';
import PosterImage from './components/PosterImage';
import TmdbAttribution from './components/TmdbAttribution';

test('renders its fallback when no poster URL is available', () => {
  render(<PosterImage alt="Example poster" fallback={<div>Poster unavailable</div>} />);
  expect(screen.getByText('Poster unavailable')).toBeInTheDocument();
});

test('replaces a poster with its fallback when loading fails', () => {
  render(
    <PosterImage
      src="https://example.invalid/missing.jpg"
      alt="Missing poster"
      fallback={<div>Poster unavailable</div>}
    />
  );

  fireEvent.error(screen.getByRole('img', { name: 'Missing poster' }));
  expect(screen.getByText('Poster unavailable')).toBeInTheDocument();
});

test('shows the required TMDB attribution', () => {
  render(<TmdbAttribution />);
  expect(screen.getByAltText('The Movie Database')).toBeInTheDocument();
  expect(screen.getByText(/not endorsed or certified by TMDB/i)).toBeInTheDocument();
});
