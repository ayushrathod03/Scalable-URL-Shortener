import { useState } from 'react';
import { ShortenerForm } from './components/ShortenerForm';
import { MetricsDashboard } from './components/MetricsDashboard';
import type { URLResponse } from './types';

function App() {
  const [selectedToken, setSelectedToken] = useState<string | null>(null);
  const [recentLinks, setRecentLinks] = useState<URLResponse[]>([]);

  const handleShortenSuccess = (newUrl: URLResponse) => {
    setRecentLinks((prev) => [newUrl, ...prev].slice(0, 10)); // Keep last 10
    setSelectedToken(newUrl.short_token); // Automatically select newly created link for analytics
  };

  return (
    <div className="container">
      {/* Header Panel */}
      <header>
        <div>
          <h1>URL Shortener & Telemetry</h1>
          <p className="subtitle" style={{ marginBottom: 0 }}>
            High-Throughput Redirection Engine & Distributed Analytics Pipeline
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <span className="badge badge-teal">Distributed Stack</span>
          <span className="badge">Prometheus Scraped</span>
        </div>
      </header>

      {/* Primary Dashboard Grid Layout */}
      <div className="layout-grid">
        {/* Left Side: Generator & Recent Links */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
          <ShortenerForm onShortenSuccess={handleShortenSuccess} />

          {/* Recent Links Selector */}
          <div className="glass-card">
            <h2>
              <span style={{ color: 'var(--accent-violet)' }}>🔗</span>
              Session Links
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              Select a generated link below to inspect its sub-millisecond click analytics.
            </p>

            <div className="list-container">
              {recentLinks.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '20px 0' }}>
                  No links generated in this session yet.
                </div>
              ) : (
                recentLinks.map((link) => (
                  <div
                    key={link.short_token}
                    className={`list-item ${selectedToken === link.short_token ? 'active' : ''}`}
                    onClick={() => setSelectedToken(link.short_token)}
                  >
                    <div className="list-item-main">
                      <span className="list-item-title">{link.short_token}</span>
                      <span className="list-item-subtitle">{link.short_url}</span>
                    </div>
                    <span className="badge badge-teal" style={{ fontSize: '0.75rem' }}>
                      Inspect ➔
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Side: Charts & Metrics Dashboard */}
        <div>
          <MetricsDashboard 
            selectedToken={selectedToken} 
            onClearSelection={() => setSelectedToken(null)} 
          />
        </div>
      </div>
    </div>
  );
}

export default App;
