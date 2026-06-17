import React, { useRef, useEffect } from 'react';
import type { CountryClickCount } from '../types';

interface GeoChartProps {
  data: CountryClickCount[];
}

const PALETTE = [
  'hsl(263, 90%, 65%)', // Violet
  'hsl(172, 90%, 50%)', // Teal
  'hsl(20, 95%, 60%)',  // Coral
  'hsl(45, 95%, 55%)',  // Gold
  'hsl(200, 90%, 60%)', // Blue
  'hsl(320, 85%, 60%)', // Pink
];

export const GeoChart: React.FC<GeoChartProps> = ({ data }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resizeCanvas = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      const width = rect?.width || 400;
      const height = rect?.height || 250;
      
      const dpr = window.devicePixelRatio || 1;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.scale(dpr, dpr);
      
      drawDonut(width, height);
    };

    const drawDonut = (width: number, height: number) => {
      ctx.clearRect(0, 0, width, height);

      const filteredData = data.filter(d => d.clicks > 0);

      // Default empty state
      if (!filteredData || filteredData.length === 0) {
        ctx.fillStyle = 'hsl(215, 12%, 50%)';
        ctx.font = '14px Outfit';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('No geographic logs recorded', width / 2, height / 2);
        return;
      }

      const totalClicks = filteredData.reduce((sum, item) => sum + item.clicks, 0);

      // Coordinates for center
      const chartPaddingLeft = 15;
      const donutRadius = Math.min(width * 0.45, height * 0.75) / 2;
      const centerX = donutRadius + chartPaddingLeft;
      const centerY = height / 2;
      
      // Draw Donut segments
      let startAngle = -Math.PI / 2; // Start at top
      
      filteredData.forEach((item, index) => {
        const sliceAngle = (item.clicks / totalClicks) * 2 * Math.PI;
        const color = PALETTE[index % PALETTE.length];
        
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.arc(centerX, centerY, donutRadius, startAngle, startAngle + sliceAngle);
        ctx.closePath();
        
        ctx.fillStyle = color;
        ctx.fill();
        
        startAngle += sliceAngle;
      });

      // Draw Inner Cutout Circle (gives Donut effect)
      ctx.beginPath();
      ctx.arc(centerX, centerY, donutRadius * 0.6, 0, 2 * Math.PI);
      ctx.fillStyle = 'hsl(222, 47%, 7%)'; // Background color matches canvas back
      ctx.fill();

      // Draw Legend on the right side
      const legendX = centerX + donutRadius + 25;
      const legendStartY = centerY - (filteredData.length * 20) / 2 + 5;
      
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      
      filteredData.slice(0, 6).forEach((item, index) => {
        const y = legendStartY + index * 22;
        const color = PALETTE[index % PALETTE.length];
        const pct = ((item.clicks / totalClicks) * 100).toFixed(0);

        // Color Block
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.roundRect ? ctx.roundRect(legendX, y - 6, 12, 12, 3) : ctx.rect(legendX, y - 6, 12, 12);
        ctx.fill();

        // Label
        ctx.fillStyle = 'hsl(215, 20%, 75%)';
        ctx.font = '500 12px Outfit';
        ctx.fillText(item.country, legendX + 20, y);

        // Value
        ctx.fillStyle = 'hsl(0, 0%, 98%)';
        ctx.font = '700 12px Outfit';
        ctx.fillText(`${pct}%`, legendX + 70, y);
      });
    };

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
