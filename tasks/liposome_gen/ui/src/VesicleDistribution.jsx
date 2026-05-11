import React, { useEffect, useState, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

// Fixed X-axis bins, consistent with old system np.linspace(5, 25, 40) and backend liposome_size_bins
// Backend bins: range(50, 255, 5) / 10 => 5.0, 5.5, 6.0, ..., 25.0 (step size 0.5)
const FIXED_BINS = [];
for (let i = 50; i < 250; i += 5) {
    FIXED_BINS.push((i / 10).toFixed(1));
}

// Generate default empty data (count is 0 for all bins)
const EMPTY_DATA = FIXED_BINS.map(size => ({ size, count: 0 }));

// Fixed displayed X-axis ticks (display one every 2.0 to avoid being too dense)
const FIXED_TICKS = FIXED_BINS.filter((_, i) => i % 4 === 0);

const VesicleDistribution = () => {
    const [data, setData] = useState(EMPTY_DATA);
    const [recognitionNum, setRecognitionNum] = useState(0);
    const [recognitionModeNum, setRecognitionModeNum] = useState(0);
    const [total, setTotal] = useState(0);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await fetch('/distribution/data');
                const result = await response.json();
                const histogram = result.histogram || [];
                // Use data if returned by backend, otherwise keep default empty data
                setData(histogram.length > 0 ? histogram : EMPTY_DATA);
                setRecognitionNum(result.recognition_num || 0);
                setRecognitionModeNum(result.recognition_mode_num || 0);
                setTotal(result.total_count || 0);
            } catch (error) {
                console.error('Failed to fetch distribution data:', error);
            }
        };

        fetchData();
        const interval = setInterval(fetchData, 1000);
        return () => clearInterval(interval);
    }, []);

    // Calculate max value of Y-axis, ensure it displays at least up to 10
    const yMax = useMemo(() => {
        const maxCount = Math.max(...data.map(d => d.count), 0);
        return Math.max(maxCount + 2, 10);
    }, [data]);

    return (
        <div className="h-full flex flex-col bg-white rounded-lg p-4">
            <div className="mb-3">
                <h3 className="text-base font-semibold text-gray-800 mb-2">Size Distribution</h3>
                <div className="flex gap-4 text-xs text-gray-600">
                    <span>Count (avg): <strong className="text-gray-900">{recognitionNum}</strong></span>
                    <span>Size (mode): <strong className="text-gray-900">{recognitionModeNum}um</strong></span>
                    <span>Total: <strong className="text-gray-900">{total}</strong></span>
                </div>
            </div>
            <div className="flex-1 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                        <XAxis
                            dataKey="size"
                            ticks={FIXED_TICKS}
                            tick={{ fill: '#6b7280', fontSize: 11 }}
                            stroke="#d1d5db"
                        />
                        <YAxis
                            domain={[0, yMax]}
                            allowDataOverflow={true}
                            tick={{ fill: '#6b7280', fontSize: 11 }}
                            stroke="#d1d5db"
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: 'white',
                                border: '1px solid #e5e7eb',
                                borderRadius: '6px',
                                fontSize: '12px'
                            }}
                        />
                        <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default VesicleDistribution;
