import React, { useState, useEffect } from 'react';
import type { URLAnalyticsResponse, GlobalAnalyticsResponse } from '../types';
import { TimelineChart } from './TimelineChart';
import { GeoChart } from './GeoChart';

interface MetricsDashboardProps {
  selectedToken: string | null;
  onClearSelection: () => void;
}

export const MetricsDashboard: React.FC<MetricsDashboardProps> = ({
  selectedToken,
  onClearSelection,
}) => {
  const [globalStats, setGlobalStats] = useState<GlobalAnalyticsResponse | null>(null);
  const [linkStats, setLinkStats] = useState<URLAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      const url = selectedToken 
        ? `/api/v1/analytics/${selectedToken}` 
        : '/api/v1/analytics';
        
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error('Failed to retrieve analytics metrics');
      }

      const data = await response.json();
      if (selectedToken) {
        setLinkStats(data);
        setGlobalStats(null);
      } else {
        setGlobalStats(data);
        setLinkStats(null);
      }
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Error loading analytics.');
    } finally {
      setLoading(false);
    }
  };

  // Poll for analytics updates every 5 seconds
  useEffect(() => {
    setLoading(true);
    fetchStats();
    
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, [selectedToken]);

  if (loading && !globalStats && !linkStats) {
    return (
      <div className="glass-card" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <div className="spinner" />
        <span style={{ marginLeft: '12px', color: 'var(--text-secondary)' }}>Loading Real-Time Analytics...</span>
      </div>
    );
  }

  // Determine current active metrics
  const totalClicks = selectedToken ? linkStats?.total_clicks : globalStats?.total_clicks;
  const timelineData = selectedToken ? linkStats?.clicks_over_time : globalStats?.clicks_over_time;
  const geoData = selectedToken ? linkStats?.geo_distribution : globalStats?.geo_distribution;

  return (
    <div className="glass-card" style={{ height: '100%' }}>
      <div className="chart-header">
        <div>
          <h2>
            <span style={{ color: 'var(--accent-teal)' }}>📊</span>
            {selectedToken ? 'Link Analytics' : 'Global Analytics'}
          </h2>
          {selectedToken && linkStats && (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', wordBreak: 'break-all' }}>
              Target: {linkStats.long_url}
            </p>
          )}
        </div>
        {selectedToken ? (
          <button className="badge badge-teal" style={{ cursor: 'pointer', border: 'none' }} onClick={onClearSelection}>
            Close Link View ✖
          </button>
        ) : (
          <span className="badge">System Live</span>
        )}
      </div>

      {error && <div className="error-message" style={{ marginBottom: '16px' }}>⚠️ {error}</div>}

      {/* Metrics Cards */}
      <div className="metrics-summary-grid">
        {!selectedToken && globalStats && (
          <div className="metric-card">
            <span className="metric-label">Short URLs Created</span>
            <span className="metric-value">{globalStats.total_urls}</span>
          </div>
        )}
        <div className="metric-card accented">
          <span className="metric-label">Total Redirect Clicks</span>
          <span className="metric-value">{totalClicks ?? 0}</span>
        </div>
        {selectedToken && linkStats && (
          <div className="metric-card">
            <span className="metric-label">Link Status</span>
            <span className="metric-value" style={{ fontSize: '1.25rem', paddingTop: '10px' }}>
              {linkStats.expires_at && new Date(linkStats.expires_at) < new Date() ? (
                <span style={{ color: 'hsl(0, 85%, 65%)' }}>Expired</span>
              ) : (
                <span style={{ color: 'var(--accent-teal)' }}>Active</span>
              )}
            </span>
          </div>
        )}
      </div>

      {/* Charts Grid */}
      <div className="charts-grid">
        <div className="chart-container">
          <div className="chart-header">
            <span className="chart-title">Redirection Timeline (Last 30 Days)</span>
          </div>
          <TimelineChart data={timelineData || []} />
        </div>

        <div className="chart-container">
          <div className="chart-header">
            <span className="chart-title">Geographical Origins</span>
          </div>
          <GeoChart data={geoData || []} />
        </div>
      </div>
    </div>
  );
};
