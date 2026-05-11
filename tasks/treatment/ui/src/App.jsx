import React from 'react';
import AgentApp from '../../../../system/components/base/agent/ui/src/App.jsx';
import VideoStream from '../../../../system/components/base/camera/ui/VideoStream.jsx';
import TreatmentTimer from './TreatmentTimer.jsx';
import './index.css';

const App = () => {
    return (
        <div className="container">
            {/* Left Panel - AI Chat */}
            <div className="left-panel">
                <div className="chat-section">
                    <AgentApp />
                </div>
            </div>

            {/* Right Panel - Video + Components */}
            <div className="right-panel">
                {/* Video Section */}
                <div className="video-section">
                    <VideoStream src="http://127.0.0.1:8889/test" />
                </div>

                {/* Timer Section */}
                <div className="component-section">
                    <TreatmentTimer />
                </div>
            </div>
        </div>
    );
};

export default App;
