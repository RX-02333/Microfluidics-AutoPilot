import React, { useEffect, useState } from 'react';

const TreatmentTimer = () => {
    const [timeLeft, setTimeLeft] = useState(15 * 60); // Initial 15 minutes
    const [isInitialized, setIsInitialized] = useState(false);

    useEffect(() => {
        const pollStatus = async () => {
            try {
                const response = await fetch('/status');
                const data = await response.json();

                // Only update after valid data is fetched
                if (data.timer_remaining !== undefined && data.timer_remaining !== null) {
                    setTimeLeft(data.timer_remaining);
                    setIsInitialized(true);
                } else if (!isInitialized) {
                    // If no data returned from backend, keep initial 15 minutes
                    setTimeLeft(15 * 60);
                }
            } catch (error) {
                console.error('Failed to fetch status:', error);
            }
        };

        pollStatus();
        const interval = setInterval(pollStatus, 1000);
        return () => clearInterval(interval);
    }, [isInitialized]);

    const formatTime = (seconds) => {
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    };

    return (
        <div style={{
            height: '100%',
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#fff',
            borderRadius: '8px',
            padding: '20px',
            boxSizing: 'border-box',
            overflow: 'hidden'
        }}>
            <div style={{ textAlign: 'center', maxWidth: '100%' }}>
                {timeLeft > 0 ? (
                    <>
                        <div style={{
                            fontSize: '48px',
                            fontWeight: 'bold',
                            color: '#10b981',
                            fontFamily: 'monospace',
                            lineHeight: 1
                        }}>
                            {formatTime(timeLeft)}
                        </div>
                        <div style={{
                            fontSize: '14px',
                            color: '#9ca3af',
                            marginTop: '8px'
                        }}>
                            Treatment Timer
                        </div>
                    </>
                ) : (
                    <div style={{
                        fontSize: '20px',
                        fontWeight: '600',
                        color: '#10b981',
                        wordBreak: 'break-word'
                    }}>
                        Treatment Complete
                    </div>
                )}
            </div>
        </div>
    );
};

export default TreatmentTimer;
