import React from 'react';
import AgentApp from '../../../../system/components/base/agent/ui/src/App.jsx';
import VideoStream from '../../../../system/components/base/camera/ui/VideoStream.jsx';
import VesicleDistribution from './VesicleDistribution.jsx';
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

            {/* Right Panel - Video + Chart */}
            <div className="right-panel">
                {/* Video Section */}
                <div className="video-section">
                    <VideoStream src="http://192.168.31.176:8889/test" />
                </div>

                {/* Vesicle Distribution Chart */}
                <div className="component-section">
                    <VesicleDistribution />
                </div>
            </div>
        </div>
    );
};

export default App;
