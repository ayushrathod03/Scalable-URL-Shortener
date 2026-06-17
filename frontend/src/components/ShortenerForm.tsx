import React, { useState } from 'react';
import type { URLResponse } from '../types';

interface ShortenerFormProps {
  onShortenSuccess: (newUrl: URLResponse) => void;
}

export const ShortenerForm: React.FC<ShortenerFormProps> = ({ onShortenSuccess }) => {
  const [longUrl, setLongUrl] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<URLResponse | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    setCopied(false);

    // Simple validation
    if (!longUrl) {
      setError('Please provide a URL to shorten.');
      return;
    }

    if (!longUrl.startsWith('http://') && !longUrl.startsWith('https://')) {
      setError('URL must start with http:// or https://');
      return;
    }

    setIsLoading(true);

    try {
      const response = await fetch('/api/v1/shorten', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          long_url: longUrl,
          expires_at: expiryDate ? new Date(expiryDate).toISOString() : null,
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to shorten URL');
      }

      const data: URLResponse = await response.json();
      setResult(data);
      setLongUrl('');
      setExpiryDate('');
      onShortenSuccess(data);
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred.');
    } finally {
      setIsLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.short_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="glass-card">
      <h2>
        <span style={{ color: 'var(--accent-violet)' }}>⚡</span>
        Generate Short Link
      </h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '20px' }}>
        Create clean, fast-redirecting short URLs with optional automatic expirations.
      </p>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="long-url">Destination URL</label>
          <input
            id="long-url"
            type="url"
            placeholder="https://example.com/very-long-link-to-shorten"
            value={longUrl}
            onChange={(e) => setLongUrl(e.target.value)}
            disabled={isLoading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="expiry-date">Optional Expiration</label>
          <input
            id="expiry-date"
            type="datetime-local"
            value={expiryDate}
            onChange={(e) => setExpiryDate(e.target.value)}
            disabled={isLoading}
            min={new Date().toISOString().slice(0, 16)}
          />
        </div>

        {error && <div className="error-message">⚠️ {error}</div>}

        <button type="submit" className="btn" style={{ width: '100%', marginTop: '10px' }} disabled={isLoading}>
          {isLoading ? (
            <span className="loading-pulse">Creating...</span>
          ) : (
            <>
              Shorten URL
              <span>➔</span>
            </>
          )}
        </button>
      </form>

      {result && (
        <div className="result-card">
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--accent-violet)' }}>
            🎉 Short Link Created!
          </h3>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            It is live and ready to route clicks.
          </p>

          <div className="link-output-group">
            <input type="text" readOnly value={result.short_url} />
            <button className="btn" style={{ padding: '10px 16px', fontSize: '0.85rem' }} onClick={copyToClipboard}>
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>

          <div style={{ marginTop: '12px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Target: <span style={{ wordBreak: 'break-all' }}>{result.long_url}</span>
            {result.expires_at && (
              <div style={{ marginTop: '4px' }}>
                Expires: {new Date(result.expires_at).toLocaleString()}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
