import React, { useRef, useEffect } from 'react';
import type { DailyClickCount } from '../types';

interface TimelineChartProps {
  data: DailyClickCount[];
}

export const TimelineChart: React.FC<TimelineChartProps> = ({ data }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Handle resizing & high DPI (Retina displays)
    const resizeCanvas = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      const width = rect?.width || 400;
      const height = rect?.height || 250;
      
      const dpr = window.devicePixelRatio || 1;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.scale(dpr, dpr);
      
      drawChart(width, height);
    };

    const drawChart = (width: number, height: number) => {
      // Clear canvas
      ctx.clearRect(0, 0, width, height);

      // Default empty state
      if (!data || data.length === 0) {
        ctx.fillStyle = 'hsl(215, 12%, 50%)';
        ctx.font = '14px Outfit';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('No telemetry data recorded yet', width / 2, height / 2);
        return;
      }

      // Chart Padding
      const padding = { top: 20, right: 20, bottom: 40, left: 45 };
      const graphWidth = width - padding.left - padding.right;
      const graphHeight = height - padding.top - padding.bottom;

      // Extract details
      const values = data.map(d => d.clicks);
      const labels = data.map(d => {
        // Format date string, e.g. "2026-06-17" -> "06/17"
        const parts = d.date.split('-');
        return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : d.date;
      });

      const maxVal = Math.max(...values, 5); // Default max bounds at least 5
      const roundedMaxVal = Math.ceil(maxVal / 5) * 5;

      // Draw Grid Lines (Y-Axis ticks)
      const yTicksCount = 4;
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
      ctx.lineWidth = 1;
      ctx.fillStyle = 'hsl(215, 20%, 50%)';
      ctx.font = '10px Outfit';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';

      for (let i = 0; i <= yTicksCount; i++) {
        const val = (roundedMaxVal / yTicksCount) * i;
        const y = padding.top + graphHeight - (val / roundedMaxVal) * graphHeight;
        
        // Horizontal line
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(padding.left + graphWidth, y);
        ctx.stroke();

        // Label
        ctx.fillText(Math.round(val).toString(), padding.left - 10, y);
      }

      // Draw X-Axis Ticks
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const xTicksCount = Math.min(labels.length, 6);
      const step = Math.max(1, Math.floor(labels.length / xTicksCount));

      for (let i = 0; i < labels.length; i += step) {
        const x = padding.left + (i / Math.max(1, labels.length - 1)) * graphWidth;
        ctx.fillText(labels[i], x, padding.top + graphHeight + 10);
      }

      // Calculate Coordinates
      const points = data.map((d, i) => {
        const x = padding.left + (i / Math.max(1, data.length - 1)) * graphWidth;
        const y = padding.top + graphHeight - (d.clicks / roundedMaxVal) * graphHeight;
        return { x, y };
      });

      // Draw Fill Gradient under line
      if (points.length > 1) {
        ctx.beginPath();
        ctx.moveTo(points[0].x, padding.top + graphHeight);
        
        // Draw bezier curves for smooth styling
        for (let i = 0; i < points.length - 1; i++) {
          const p0 = points[i];
          const p1 = points[i + 1];
          const cpX1 = p0.x + (p1.x - p0.x) / 2;
          const cpY1 = p0.y;
          const cpX2 = p0.x + (p1.x - p0.x) / 2;
          const cpY2 = p1.y;
          ctx.bezierCurveTo(cpX1, cpY1, cpX2, cpY2, p1.x, p1.y);
        }
        
        ctx.lineTo(points[points.length - 1].x, padding.top + graphHeight);
        ctx.closePath();

        const fillGrad = ctx.createLinearGradient(0, padding.top, 0, padding.top + graphHeight);
        fillGrad.addColorStop(0, 'rgba(138, 43, 226, 0.25)'); // Violet glow
        fillGrad.addColorStop(1, 'rgba(138, 43, 226, 0.0)');
        ctx.fillStyle = fillGrad;
        ctx.fill();
      }

      // Draw Main Line
      if (points.length > 0) {
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);

        if (points.length === 1) {
          ctx.lineTo(padding.left + graphWidth, points[0].y);
        } else {
          for (let i = 0; i < points.length - 1; i++) {
            const p0 = points[i];
            const p1 = points[i + 1];
            const cpX1 = p0.x + (p1.x - p0.x) / 2;
            const cpY1 = p0.y;
            const cpX2 = p0.x + (p1.x - p0.x) / 2;
            const cpY2 = p1.y;
            ctx.bezierCurveTo(cpX1, cpY1, cpX2, cpY2, p1.x, p1.y);
          }
        }

        const lineGrad = ctx.createLinearGradient(padding.left, 0, padding.left + graphWidth, 0);
        lineGrad.addColorStop(0, 'hsl(263, 90%, 65%)'); // Violet
        lineGrad.addColorStop(1, 'hsl(172, 90%, 50%)'); // Teal
        ctx.strokeStyle = lineGrad;
        ctx.lineWidth = 3;
        ctx.lineCap = 'round';
        ctx.stroke();
      }

      // Draw data points
      points.forEach((p) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4, 0, 2 * Math.PI);
        ctx.fillStyle = 'hsl(172, 90%, 50%)'; // Teal dot
        ctx.strokeStyle = 'hsl(222, 47%, 7%)';
        ctx.lineWidth = 2;
        ctx.fill();
        ctx.stroke();
      });
    };

    // Initialize and attach listeners
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    return () => {
      window.removeEventListener('resize', resizeCanvas);
    };
  }, [data]);

  return (
    <div className="canvas-wrapper">
      <canvas ref={canvasRef} />
    </div>
  );
};
